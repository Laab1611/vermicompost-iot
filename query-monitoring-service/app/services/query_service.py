from datetime import UTC, datetime, timedelta
import logging
import unicodedata

from sqlalchemy import and_, desc, func, literal
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, PersistenceError, ValidationError
from app.models.query_model import CamaVermicompostaje, Lectura, LecturaInvalida, NodoSensor, TipoVariable

MAX_QUERY_LIMIT = 1000
MAX_MINUTES_WINDOW = 60 * 24 * 30
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


def _validate_limit(limit: int) -> None:
    if limit < 1 or limit > MAX_QUERY_LIMIT:
        raise ValidationError(f"limit debe estar entre 1 y {MAX_QUERY_LIMIT}")


def _validate_minutes(minutes: int) -> None:
    if minutes < 1 or minutes > MAX_MINUTES_WINDOW:
        raise ValidationError(f"minutes debe estar entre 1 y {MAX_MINUTES_WINDOW}")


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _validate_range(start: datetime, end: datetime) -> None:
    if _to_naive_utc(start) > _to_naive_utc(end):
        raise ValidationError("start no puede ser mayor que end")


def _normalize_tipo_variable(nombre: str | None) -> str | None:
    if not nombre:
        return None

    normalized = unicodedata.normalize("NFKD", nombre)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char)).strip().lower()
    compact = normalized.replace(" ", "")

    if "temperatura" in normalized:
        return "temperatura"
    if "humedad" in normalized:
        return "humedad"
    if compact == "ph" or "ph" in compact:
        return "ph"
    return None


def _get_nodo_or_fail(db: Session, nodo_id: int) -> NodoSensor:
    nodo = db.query(NodoSensor).filter(NodoSensor.nodo_id == nodo_id).first()
    if not nodo:
        raise NotFoundError("nodo no encontrado")
    return nodo


def _get_cama_or_fail(db: Session, cama_id: int) -> CamaVermicompostaje:
    cama = db.query(CamaVermicompostaje).filter(CamaVermicompostaje.cama_id == cama_id).first()
    if not cama:
        raise NotFoundError("cama no encontrada")
    return cama


def _get_tipo_or_fail(db: Session, tipo_variable_id: int) -> TipoVariable:
    tipo = db.query(TipoVariable).filter(TipoVariable.tipo_variable_id == tipo_variable_id).first()
    if not tipo:
        raise NotFoundError("tipo_variable no encontrado")
    return tipo


def list_camas(db: Session) -> list[CamaVermicompostaje]:
    try:
        rows = db.query(CamaVermicompostaje).order_by(CamaVermicompostaje.cama_id.asc()).all()
        logger.debug("Query list_camas returned count=%s", len(rows))
        return rows
    except SQLAlchemyError as exc:
        logger.exception("Query list_camas failed")
        raise PersistenceError("error al consultar camas") from exc


def list_nodos(db: Session) -> list[NodoSensor]:
    try:
        rows = db.query(NodoSensor).order_by(NodoSensor.nodo_id.asc()).all()
        logger.debug("Query list_nodos returned count=%s", len(rows))
        return rows
    except SQLAlchemyError as exc:
        logger.exception("Query list_nodos failed")
        raise PersistenceError("error al consultar nodos") from exc


def list_tipos_variable(db: Session) -> list[TipoVariable]:
    try:
        rows = db.query(TipoVariable).order_by(TipoVariable.tipo_variable_id.asc()).all()
        logger.debug("Query list_tipos_variable returned count=%s", len(rows))
        return rows
    except SQLAlchemyError as exc:
        logger.exception("Query list_tipos_variable failed")
        raise PersistenceError("error al consultar tipos de variable") from exc


def _lectura_rows(query):
    return query.with_entities(
        Lectura.lectura_id,
        Lectura.nodo_id,
        NodoSensor.cama_id,
        NodoSensor.codigo_nodo,
        Lectura.tipo_variable_id,
        TipoVariable.nombre,
        TipoVariable.unidad_medida,
        Lectura.valor,
        Lectura.fecha_medicion,
        Lectura.fecha_recepcion,
        literal(True).label("es_valida"),
        literal(None).label("motivo_invalidacion"),
    )


def _base_lectura_query(db: Session):
    return (
        db.query(Lectura)
        .join(NodoSensor, NodoSensor.nodo_id == Lectura.nodo_id)
        .join(TipoVariable, TipoVariable.tipo_variable_id == Lectura.tipo_variable_id)
    )


def _base_lectura_invalida_query(db: Session):
    return (
        db.query(LecturaInvalida)
        .outerjoin(NodoSensor, NodoSensor.nodo_id == LecturaInvalida.nodo_id)
        .outerjoin(TipoVariable, TipoVariable.tipo_variable_id == LecturaInvalida.tipo_variable_id)
    )


def _lectura_invalida_rows(query):
    return query.with_entities(
        LecturaInvalida.lectura_invalida_id.label("lectura_id"),
        LecturaInvalida.nodo_id,
        NodoSensor.cama_id,
        NodoSensor.codigo_nodo,
        LecturaInvalida.tipo_variable_id,
        TipoVariable.nombre,
        TipoVariable.unidad_medida,
        LecturaInvalida.valor_recibido,
        LecturaInvalida.fecha_medicion,
        LecturaInvalida.fecha_recepcion,
        literal(False).label("es_valida"),
        LecturaInvalida.tipo_error.label("motivo_invalidacion"),
    )


def get_lecturas_by_nodo(db: Session, nodo_id: int, limit: int = 200):
    _validate_limit(limit)
    logger.debug("Query get_lecturas_by_nodo start nodo_id=%s limit=%s", nodo_id, limit)
    try:
        _get_nodo_or_fail(db, nodo_id)
        query = _base_lectura_query(db).filter(Lectura.nodo_id == nodo_id)
        rows = _lectura_rows(query).order_by(desc(Lectura.fecha_medicion)).limit(limit).all()
        logger.debug("Query get_lecturas_by_nodo returned count=%s nodo_id=%s", len(rows), nodo_id)
        return rows
    except (NotFoundError, ValidationError):
        logger.warning("Query get_lecturas_by_nodo validation/notfound nodo_id=%s", nodo_id)
        raise
    except SQLAlchemyError as exc:
        logger.exception("Query get_lecturas_by_nodo failed nodo_id=%s", nodo_id)
        raise PersistenceError("error al consultar lecturas por nodo") from exc


def get_lecturas_by_cama(db: Session, cama_id: int, limit: int = 200):
    _validate_limit(limit)
    logger.debug("Query get_lecturas_by_cama start cama_id=%s limit=%s", cama_id, limit)
    try:
        _get_cama_or_fail(db, cama_id)
        query = _base_lectura_query(db).filter(NodoSensor.cama_id == cama_id)
        rows = _lectura_rows(query).order_by(desc(Lectura.fecha_medicion)).limit(limit).all()
        logger.debug("Query get_lecturas_by_cama returned count=%s cama_id=%s", len(rows), cama_id)
        return rows
    except (NotFoundError, ValidationError):
        logger.warning("Query get_lecturas_by_cama validation/notfound cama_id=%s", cama_id)
        raise
    except SQLAlchemyError as exc:
        logger.exception("Query get_lecturas_by_cama failed cama_id=%s", cama_id)
        raise PersistenceError("error al consultar lecturas por cama") from exc


def get_lecturas_by_tipo_variable(db: Session, tipo_variable_id: int, limit: int = 200):
    _validate_limit(limit)
    logger.debug(
        "Query get_lecturas_by_tipo_variable start tipo_variable_id=%s limit=%s",
        tipo_variable_id,
        limit,
    )
    try:
        _get_tipo_or_fail(db, tipo_variable_id)
        query = _base_lectura_query(db).filter(Lectura.tipo_variable_id == tipo_variable_id)
        rows = _lectura_rows(query).order_by(desc(Lectura.fecha_medicion)).limit(limit).all()
        logger.debug(
            "Query get_lecturas_by_tipo_variable returned count=%s tipo_variable_id=%s",
            len(rows),
            tipo_variable_id,
        )
        return rows
    except (NotFoundError, ValidationError):
        logger.warning(
            "Query get_lecturas_by_tipo_variable validation/notfound tipo_variable_id=%s",
            tipo_variable_id,
        )
        raise
    except SQLAlchemyError as exc:
        logger.exception("Query get_lecturas_by_tipo_variable failed tipo_variable_id=%s", tipo_variable_id)
        raise PersistenceError("error al consultar lecturas por tipo de variable") from exc


def get_lecturas_by_rango(db: Session, start: datetime, end: datetime, limit: int = 300):
    _validate_limit(limit)
    _validate_range(start, end)
    logger.debug("Query get_lecturas_by_rango start start=%s end=%s limit=%s", start, end, limit)
    try:
        query = _base_lectura_query(db).filter(Lectura.fecha_medicion >= start, Lectura.fecha_medicion <= end)
        rows = _lectura_rows(query).order_by(desc(Lectura.fecha_medicion)).limit(limit).all()
        logger.debug("Query get_lecturas_by_rango returned count=%s", len(rows))
        return rows
    except (ValidationError,):
        logger.warning("Query get_lecturas_by_rango validation error start=%s end=%s", start, end)
        raise
    except SQLAlchemyError as exc:
        logger.exception("Query get_lecturas_by_rango failed")
        raise PersistenceError("error al consultar lecturas por rango") from exc


def get_lecturas_invalidas(db: Session, limit: int = 300):
    _validate_limit(limit)
    logger.debug("Query get_lecturas_invalidas start limit=%s", limit)
    try:
        query = _base_lectura_invalida_query(db)
        rows = _lectura_invalida_rows(query).order_by(desc(LecturaInvalida.fecha_recepcion)).limit(limit).all()
        logger.debug("Query get_lecturas_invalidas returned count=%s", len(rows))
        return rows
    except (ValidationError,):
        logger.warning("Query get_lecturas_invalidas validation error limit=%s", limit)
        raise
    except SQLAlchemyError as exc:
        logger.exception("Query get_lecturas_invalidas failed")
        raise PersistenceError("error al consultar lecturas invalidas") from exc


def get_nodos_desconectados(db: Session, minutes: int = 15) -> list[NodoSensor]:
    _validate_minutes(minutes)
    logger.debug("Query get_nodos_desconectados start minutes=%s", minutes)
    try:
        threshold = datetime.now(UTC) - timedelta(minutes=minutes)
        rows = (
            db.query(NodoSensor)
            .filter((NodoSensor.ultima_lectura_recibida.is_(None)) | (NodoSensor.ultima_lectura_recibida < threshold))
            .order_by(NodoSensor.nodo_id.asc())
            .all()
        )
        logger.debug("Query get_nodos_desconectados returned count=%s minutes=%s", len(rows), minutes)
        return rows
    except (ValidationError,):
        logger.warning("Query get_nodos_desconectados validation error minutes=%s", minutes)
        raise
    except SQLAlchemyError as exc:
        logger.exception("Query get_nodos_desconectados failed minutes=%s", minutes)
        raise PersistenceError("error al consultar nodos desconectados") from exc


def _is_connected(last_seen: datetime | None, minutes: int) -> bool:
    if not last_seen:
        return False
    if last_seen.tzinfo is None:
        threshold = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=minutes)
        return last_seen >= threshold
    threshold = datetime.now(UTC) - timedelta(minutes=minutes)
    return last_seen >= threshold


def _latest_readings_by_nodo(db: Session, nodo_id: int) -> dict[str, float]:
    try:
        rows = (
            db.query(Lectura, TipoVariable)
            .join(TipoVariable, TipoVariable.tipo_variable_id == Lectura.tipo_variable_id)
            .filter(Lectura.nodo_id == nodo_id)
            .order_by(TipoVariable.tipo_variable_id.asc(), Lectura.fecha_recepcion.desc())
            .all()
        )
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar ultimas lecturas por nodo") from exc
    result: dict[str, float] = {}
    for lectura, tipo in rows:
        if tipo.nombre not in result:
            result[tipo.nombre] = float(lectura.valor)
    return result


def _estado_actual_de_cama(db: Session, cama: CamaVermicompostaje, minutes: int) -> dict:
    nodos = (
        db.query(NodoSensor)
        .filter(NodoSensor.cama_id == cama.cama_id)
        .order_by(NodoSensor.nodo_id.asc())
        .all()
    )
    return {
        "cama_id": cama.cama_id,
        "nombre": cama.nombre,
        "nodos": [
            {
                "nodo_id": estado_nodo["nodo_id"],
                "codigo_nodo": estado_nodo["codigo_nodo"],
                "conectado": estado_nodo["conectado"],
            }
            for estado_nodo in (get_estado_actual_por_nodo(db, nodo.nodo_id, minutes) for nodo in nodos)
        ],
    }


def get_estado_actual_por_nodo(db: Session, nodo_id: int, minutes: int = 15) -> dict:
    _validate_minutes(minutes)
    logger.debug("Query get_estado_actual_por_nodo start nodo_id=%s minutes=%s", nodo_id, minutes)
    try:
        nodo = _get_nodo_or_fail(db, nodo_id)
        conectado = _is_connected(nodo.ultima_lectura_recibida, minutes)
        result = {
            "nodo_id": nodo.nodo_id,
            "cama_id": nodo.cama_id,
            "codigo_nodo": nodo.codigo_nodo,
            "ultima_lectura_recibida": nodo.ultima_lectura_recibida,
            "conectado": conectado,
            "lecturas_actuales": _latest_readings_by_nodo(db, nodo.nodo_id),
        }
        logger.debug(
            "Query get_estado_actual_por_nodo completed nodo_id=%s conectado=%s lecturas=%s",
            nodo_id,
            conectado,
            len(result["lecturas_actuales"]),
        )
        return result
    except (NotFoundError, ValidationError, PersistenceError):
        logger.warning("Query get_estado_actual_por_nodo failed validation/notfound nodo_id=%s", nodo_id)
        raise
    except SQLAlchemyError as exc:
        logger.exception("Query get_estado_actual_por_nodo failed nodo_id=%s", nodo_id)
        raise PersistenceError("error al consultar estado de nodo") from exc


def get_estado_actual_por_cama(db: Session, cama_id: int, minutes: int = 15) -> dict:
    _validate_minutes(minutes)
    logger.debug("Query get_estado_actual_por_cama start cama_id=%s minutes=%s", cama_id, minutes)
    try:
        cama = _get_cama_or_fail(db, cama_id)
        result = _estado_actual_de_cama(db, cama, minutes)
        logger.debug(
            "Query get_estado_actual_por_cama completed cama_id=%s nodos=%s",
            cama_id,
            len(result["nodos"]),
        )
        return result
    except (NotFoundError, ValidationError, PersistenceError):
        logger.warning("Query get_estado_actual_por_cama failed validation/notfound cama_id=%s", cama_id)
        raise
    except SQLAlchemyError as exc:
        logger.exception("Query get_estado_actual_por_cama failed cama_id=%s", cama_id)
        raise PersistenceError("error al consultar estado de cama") from exc


def get_all_camas_estado(db: Session, minutes: int = 15) -> list[dict]:
    _validate_minutes(minutes)
    logger.debug("Query get_all_camas_estado start minutes=%s", minutes)
    try:
        camas = db.query(CamaVermicompostaje).order_by(CamaVermicompostaje.cama_id.asc()).all()
        result = [_estado_actual_de_cama(db, cama, minutes) for cama in camas]
        logger.debug("Query get_all_camas_estado completed camas=%s", len(result))
        return result
    except (ValidationError, PersistenceError):
        logger.warning("Query get_all_camas_estado validation/persistence error")
        raise
    except SQLAlchemyError as exc:
        logger.exception("Query get_all_camas_estado failed")
        raise PersistenceError("error al consultar estados de camas") from exc


def get_monitoring_summary(db: Session, disconnect_minutes: int = 15) -> dict:
    _validate_minutes(disconnect_minutes)
    logger.debug("Query get_monitoring_summary start disconnect_minutes=%s", disconnect_minutes)
    try:
        total_camas = db.query(func.count(CamaVermicompostaje.cama_id)).scalar() or 0
        total_nodos = db.query(func.count(NodoSensor.nodo_id)).scalar() or 0
        threshold = datetime.now(UTC) - timedelta(minutes=disconnect_minutes)
        nodos_desconectados = (
            db.query(func.count(NodoSensor.nodo_id))
            .filter((NodoSensor.ultima_lectura_recibida.is_(None)) | (NodoSensor.ultima_lectura_recibida < threshold))
            .scalar()
            or 0
        )
        lecturas_validas = db.query(func.count(Lectura.lectura_id)).scalar() or 0
        lecturas_invalidas = db.query(func.count(LecturaInvalida.lectura_invalida_id)).scalar() or 0
        result = {
            "total_camas": total_camas,
            "total_nodos": total_nodos,
            "nodos_conectados": max(total_nodos - nodos_desconectados, 0),
            "nodos_desconectados": nodos_desconectados,
            "lecturas_validas": lecturas_validas,
            "lecturas_invalidas": lecturas_invalidas,
        }
        logger.debug(
            "Query get_monitoring_summary completed total_camas=%s total_nodos=%s nodos_desconectados=%s lecturas_invalidas=%s",
            result["total_camas"],
            result["total_nodos"],
            result["nodos_desconectados"],
            result["lecturas_invalidas"],
        )
        return result
    except (ValidationError, PersistenceError):
        logger.warning("Query get_monitoring_summary validation/persistence error")
        raise
    except SQLAlchemyError as exc:
        logger.exception("Query get_monitoring_summary failed")
        raise PersistenceError("error al consultar resumen de monitoreo") from exc


def get_invalidaciones_count_by_causa(db: Session) -> list[dict]:
    try:
        rows = (
            db.query(
                LecturaInvalida.tipo_error,
                func.count(LecturaInvalida.lectura_invalida_id).label("total"),
            )
            .group_by(LecturaInvalida.tipo_error)
            .order_by(func.count(LecturaInvalida.lectura_invalida_id).desc())
            .all()
        )
        logger.debug("Query get_invalidaciones_count_by_causa returned count=%s", len(rows))
        return [{"tipo_error": r.tipo_error, "total": r.total} for r in rows]
    except SQLAlchemyError as exc:
        logger.exception("Query get_invalidaciones_count_by_causa failed")
        raise PersistenceError("error al consultar invalidaciones por causa") from exc


def get_errores_count_by_nodo(db: Session) -> list[dict]:
    try:
        rows = (
            db.query(
                LecturaInvalida.nodo_id,
                NodoSensor.codigo_nodo,
                NodoSensor.cama_id,
                CamaVermicompostaje.nombre.label("cama_nombre"),
                func.count(LecturaInvalida.lectura_invalida_id).label("total_errores"),
            )
            .outerjoin(NodoSensor, NodoSensor.nodo_id == LecturaInvalida.nodo_id)
            .outerjoin(CamaVermicompostaje, CamaVermicompostaje.cama_id == NodoSensor.cama_id)
            .group_by(LecturaInvalida.nodo_id, NodoSensor.codigo_nodo, NodoSensor.cama_id, CamaVermicompostaje.nombre)
            .order_by(func.count(LecturaInvalida.lectura_invalida_id).desc())
            .all()
        )
        logger.debug("Query get_errores_count_by_nodo returned count=%s", len(rows))
        return [
            {
                "nodo_id": r.nodo_id,
                "codigo_nodo": r.codigo_nodo,
                "cama_id": r.cama_id,
                "cama_nombre": r.cama_nombre,
                "total_errores": r.total_errores,
            }
            for r in rows
        ]
    except SQLAlchemyError as exc:
        logger.exception("Query get_errores_count_by_nodo failed")
        raise PersistenceError("error al consultar errores por nodo") from exc


def get_all_nodos_connection_status(db: Session, minutes: int = 15) -> list[dict]:
    _validate_minutes(minutes)
    try:
        rows = (
            db.query(NodoSensor, CamaVermicompostaje.nombre)
            .join(CamaVermicompostaje, CamaVermicompostaje.cama_id == NodoSensor.cama_id)
            .order_by(NodoSensor.nodo_id.asc())
            .all()
        )
        return [
            {
                "nodo_id": nodo.nodo_id,
                "codigo_nodo": nodo.codigo_nodo,
                "cama_id": nodo.cama_id,
                "cama_nombre": cama_nombre,
                "conectado": _is_connected(nodo.ultima_lectura_recibida, minutes),
            }
            for nodo, cama_nombre in rows
        ]
    except (ValidationError,):
        raise
    except SQLAlchemyError as exc:
        logger.exception("Query get_all_nodos_connection_status failed")
        raise PersistenceError("error al consultar estado de conexion de nodos") from exc


def get_latest_sensor_averages_by_cama(db: Session) -> list[dict]:
    logger.debug("Query get_latest_sensor_averages_by_cama start")
    try:
        latest_per_nodo_tipo = (
            db.query(
                Lectura.nodo_id.label("nodo_id"),
                Lectura.tipo_variable_id.label("tipo_variable_id"),
                func.max(Lectura.fecha_recepcion).label("max_fecha_recepcion"),
            )
            .group_by(Lectura.nodo_id, Lectura.tipo_variable_id)
            .subquery()
        )

        rows = (
            db.query(
                NodoSensor.cama_id,
                CamaVermicompostaje.nombre,
                TipoVariable.nombre,
                Lectura.valor,
            )
            .join(
                latest_per_nodo_tipo,
                and_(
                    Lectura.nodo_id == latest_per_nodo_tipo.c.nodo_id,
                    Lectura.tipo_variable_id == latest_per_nodo_tipo.c.tipo_variable_id,
                    Lectura.fecha_recepcion == latest_per_nodo_tipo.c.max_fecha_recepcion,
                ),
            )
            .join(NodoSensor, NodoSensor.nodo_id == Lectura.nodo_id)
            .join(CamaVermicompostaje, CamaVermicompostaje.cama_id == NodoSensor.cama_id)
            .join(TipoVariable, TipoVariable.tipo_variable_id == Lectura.tipo_variable_id)
            .all()
        )

        aggregates: dict[int, dict] = {}
        for cama_id, cama_nombre, tipo_variable_nombre, valor in rows:
            sensor_key = _normalize_tipo_variable(tipo_variable_nombre)
            if sensor_key is None:
                continue

            entry = aggregates.setdefault(
                int(cama_id),
                {
                    "cama_id": int(cama_id),
                    "cama_nombre": str(cama_nombre),
                    "temperatura_sum": 0.0,
                    "temperatura_count": 0,
                    "humedad_sum": 0.0,
                    "humedad_count": 0,
                    "ph_sum": 0.0,
                    "ph_count": 0,
                },
            )

            entry[f"{sensor_key}_sum"] += float(valor)
            entry[f"{sensor_key}_count"] += 1

        result = []
        for item in sorted(aggregates.values(), key=lambda value: value["cama_id"]):
            temperatura = (
                item["temperatura_sum"] / item["temperatura_count"]
                if item["temperatura_count"] > 0
                else None
            )
            humedad = item["humedad_sum"] / item["humedad_count"] if item["humedad_count"] > 0 else None
            ph = item["ph_sum"] / item["ph_count"] if item["ph_count"] > 0 else None

            result.append(
                {
                    "cama_id": item["cama_id"],
                    "cama_nombre": item["cama_nombre"],
                    "temperatura": temperatura,
                    "humedad": humedad,
                    "ph": ph,
                }
            )

        logger.debug("Query get_latest_sensor_averages_by_cama completed camas=%s", len(result))
        return result
    except SQLAlchemyError as exc:
        logger.exception("Query get_latest_sensor_averages_by_cama failed")
        raise PersistenceError("error al consultar promedios de sensores por cama") from exc
