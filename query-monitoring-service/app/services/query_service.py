from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, literal
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, PersistenceError, ValidationError
from app.models.query_model import CamaVermicompostaje, Lectura, LecturaInvalida, NodoSensor, TipoVariable

MAX_QUERY_LIMIT = 1000
MAX_MINUTES_WINDOW = 60 * 24 * 30


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
        return db.query(CamaVermicompostaje).order_by(CamaVermicompostaje.cama_id.asc()).all()
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar camas") from exc


def list_nodos(db: Session) -> list[NodoSensor]:
    try:
        return db.query(NodoSensor).order_by(NodoSensor.nodo_id.asc()).all()
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar nodos") from exc


def list_tipos_variable(db: Session) -> list[TipoVariable]:
    try:
        return db.query(TipoVariable).order_by(TipoVariable.tipo_variable_id.asc()).all()
    except SQLAlchemyError as exc:
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
    try:
        _get_nodo_or_fail(db, nodo_id)
        query = _base_lectura_query(db).filter(Lectura.nodo_id == nodo_id)
        return _lectura_rows(query).order_by(desc(Lectura.fecha_medicion)).limit(limit).all()
    except (NotFoundError, ValidationError):
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar lecturas por nodo") from exc


def get_lecturas_by_cama(db: Session, cama_id: int, limit: int = 200):
    _validate_limit(limit)
    try:
        _get_cama_or_fail(db, cama_id)
        query = _base_lectura_query(db).filter(NodoSensor.cama_id == cama_id)
        return _lectura_rows(query).order_by(desc(Lectura.fecha_medicion)).limit(limit).all()
    except (NotFoundError, ValidationError):
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar lecturas por cama") from exc


def get_lecturas_by_tipo_variable(db: Session, tipo_variable_id: int, limit: int = 200):
    _validate_limit(limit)
    try:
        _get_tipo_or_fail(db, tipo_variable_id)
        query = _base_lectura_query(db).filter(Lectura.tipo_variable_id == tipo_variable_id)
        return _lectura_rows(query).order_by(desc(Lectura.fecha_medicion)).limit(limit).all()
    except (NotFoundError, ValidationError):
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar lecturas por tipo de variable") from exc


def get_lecturas_by_rango(db: Session, start: datetime, end: datetime, limit: int = 300):
    _validate_limit(limit)
    _validate_range(start, end)
    try:
        query = _base_lectura_query(db).filter(Lectura.fecha_medicion >= start, Lectura.fecha_medicion <= end)
        return _lectura_rows(query).order_by(desc(Lectura.fecha_medicion)).limit(limit).all()
    except (ValidationError,):
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar lecturas por rango") from exc


def get_lecturas_invalidas(db: Session, limit: int = 300):
    _validate_limit(limit)
    try:
        query = _base_lectura_invalida_query(db)
        return _lectura_invalida_rows(query).order_by(desc(LecturaInvalida.fecha_recepcion)).limit(limit).all()
    except (ValidationError,):
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar lecturas invalidas") from exc


def get_nodos_desconectados(db: Session, minutes: int = 15) -> list[NodoSensor]:
    _validate_minutes(minutes)
    try:
        threshold = datetime.now(UTC) - timedelta(minutes=minutes)
        return (
            db.query(NodoSensor)
            .filter((NodoSensor.ultima_lectura_recibida.is_(None)) | (NodoSensor.ultima_lectura_recibida < threshold))
            .order_by(NodoSensor.nodo_id.asc())
            .all()
        )
    except (ValidationError,):
        raise
    except SQLAlchemyError as exc:
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


def get_estado_actual_por_nodo(db: Session, nodo_id: int, minutes: int = 15) -> dict:
    _validate_minutes(minutes)
    try:
        nodo = _get_nodo_or_fail(db, nodo_id)
        conectado = _is_connected(nodo.ultima_lectura_recibida, minutes)
        return {
            "nodo_id": nodo.nodo_id,
            "cama_id": nodo.cama_id,
            "codigo_nodo": nodo.codigo_nodo,
            "ultima_lectura_recibida": nodo.ultima_lectura_recibida,
            "conectado": conectado,
            "lecturas_actuales": _latest_readings_by_nodo(db, nodo.nodo_id),
        }
    except (NotFoundError, ValidationError, PersistenceError):
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar estado de nodo") from exc


def get_estado_actual_por_cama(db: Session, cama_id: int, minutes: int = 15) -> dict:
    _validate_minutes(minutes)
    try:
        cama = _get_cama_or_fail(db, cama_id)
        nodos = db.query(NodoSensor).filter(NodoSensor.cama_id == cama_id).all()
        return {
            "cama_id": cama.cama_id,
            "nombre": cama.nombre,
            "nodos": [get_estado_actual_por_nodo(db, nodo.nodo_id, minutes) for nodo in nodos],
        }
    except (NotFoundError, ValidationError, PersistenceError):
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar estado de cama") from exc


def get_monitoring_summary(db: Session, disconnect_minutes: int = 15) -> dict:
    _validate_minutes(disconnect_minutes)
    try:
        total_camas = db.query(func.count(CamaVermicompostaje.cama_id)).scalar() or 0
        total_nodos = db.query(func.count(NodoSensor.nodo_id)).scalar() or 0
        nodos_desconectados = len(get_nodos_desconectados(db, disconnect_minutes))
        lecturas_invalidas = db.query(func.count(LecturaInvalida.lectura_invalida_id)).scalar() or 0
        return {
            "total_camas": total_camas,
            "total_nodos": total_nodos,
            "nodos_conectados": max(total_nodos - nodos_desconectados, 0),
            "nodos_desconectados": nodos_desconectados,
            "lecturas_invalidas": lecturas_invalidas,
        }
    except (ValidationError, PersistenceError):
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar resumen de monitoreo") from exc