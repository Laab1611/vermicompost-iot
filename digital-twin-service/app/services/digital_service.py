import logging

from sqlalchemy import and_, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, PersistenceError, ValidationError
from app.models.digital_model import CamaVermicompostaje, Lectura, LecturaInvalida, NodoSensor, TipoVariable

MAX_QUERY_LIMIT = 1000
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


def _validate_limit(limit: int) -> None:
    if limit < 1 or limit > MAX_QUERY_LIMIT:
        raise ValidationError(f"limit debe estar entre 1 y {MAX_QUERY_LIMIT}")


def _latest_readings_by_nodo(db: Session, nodo_id: int, limit: int = 200) -> dict[str, float]:
    _validate_limit(limit)
    logger.debug("Digital twin latest_readings_by_nodo start nodo_id=%s limit=%s", nodo_id, limit)
    try:
        readings_map = _latest_readings_by_nodos(db, [nodo_id], limit)
        result = readings_map.get(nodo_id, {})
        logger.debug(
            "Digital twin latest_readings_by_nodo completed nodo_id=%s lecturas_actuales=%s",
            nodo_id,
            len(result),
        )
        return result
    except SQLAlchemyError as exc:
        logger.exception("Digital twin latest_readings_by_nodo failed nodo_id=%s", nodo_id)
        raise PersistenceError("error al consultar lecturas del nodo") from exc


def _latest_readings_by_nodos(db: Session, nodo_ids: list[int], limit: int = 200) -> dict[int, dict[str, float]]:
    _validate_limit(limit)
    if not nodo_ids:
        return {}

    latest_per_tipo = (
        db.query(
            Lectura.nodo_id.label("nodo_id"),
            Lectura.tipo_variable_id.label("tipo_variable_id"),
            func.max(Lectura.fecha_recepcion).label("max_fecha_recepcion"),
        )
        .filter(Lectura.nodo_id.in_(nodo_ids))
        .group_by(Lectura.nodo_id, Lectura.tipo_variable_id)
        .subquery()
    )

    rows = (
        db.query(Lectura.nodo_id, TipoVariable.nombre, Lectura.valor)
        .join(
            latest_per_tipo,
            and_(
                Lectura.nodo_id == latest_per_tipo.c.nodo_id,
                Lectura.tipo_variable_id == latest_per_tipo.c.tipo_variable_id,
                Lectura.fecha_recepcion == latest_per_tipo.c.max_fecha_recepcion,
            ),
        )
        .join(TipoVariable, TipoVariable.tipo_variable_id == Lectura.tipo_variable_id)
        .all()
    )

    result: dict[int, dict[str, float]] = {nodo_id: {} for nodo_id in nodo_ids}
    for row_nodo_id, tipo_nombre, valor in rows:
        if tipo_nombre not in result[row_nodo_id]:
            result[row_nodo_id][tipo_nombre] = float(valor)

    return result


def _latest_last_seen_by_nodos(db: Session, nodo_ids: list[int]) -> dict[int, object]:
    if not nodo_ids:
        return {}

    rows = (
        db.query(Lectura.nodo_id, func.max(Lectura.fecha_recepcion))
        .filter(Lectura.nodo_id.in_(nodo_ids))
        .group_by(Lectura.nodo_id)
        .all()
    )
    return {nodo_id: last_seen for nodo_id, last_seen in rows}


def get_nodo_twin_state(db: Session, nodo_id: int, readings_limit: int = 200) -> dict:
    logger.debug("Digital twin get_nodo_twin_state start nodo_id=%s readings_limit=%s", nodo_id, readings_limit)
    try:
        nodo = db.query(NodoSensor).filter(NodoSensor.nodo_id == nodo_id).first()
        if not nodo:
            raise NotFoundError("nodo no encontrado")
        latest_last_seen = _latest_last_seen_by_nodos(db, [nodo_id])
        ultima_lectura_recibida = nodo.ultima_lectura_recibida or latest_last_seen.get(nodo_id)
        result = {
            "nodo_id": nodo.nodo_id,
            "cama_id": nodo.cama_id,
            "codigo_nodo": nodo.codigo_nodo,
            "ultima_lectura_recibida": ultima_lectura_recibida,
            "lecturas_actuales": _latest_readings_by_nodo(db, nodo_id, readings_limit),
        }
        logger.debug(
            "Digital twin get_nodo_twin_state completed nodo_id=%s lecturas_actuales=%s",
            nodo_id,
            len(result["lecturas_actuales"]),
        )
        return result
    except (NotFoundError, ValidationError, PersistenceError):
        logger.warning("Digital twin get_nodo_twin_state validation/notfound nodo_id=%s", nodo_id)
        raise
    except SQLAlchemyError as exc:
        logger.exception("Digital twin get_nodo_twin_state failed nodo_id=%s", nodo_id)
        raise PersistenceError("error al consultar estado twin de nodo") from exc


def get_cama_twin_state(db: Session, cama_id: int, readings_limit: int = 200) -> dict:
    logger.debug("Digital twin get_cama_twin_state start cama_id=%s readings_limit=%s", cama_id, readings_limit)
    try:
        _validate_limit(readings_limit)
        cama = db.query(CamaVermicompostaje).filter(CamaVermicompostaje.cama_id == cama_id).first()
        if not cama:
            raise NotFoundError("cama no encontrada")
        nodos = db.query(NodoSensor).filter(NodoSensor.cama_id == cama_id).all()
        nodo_ids = [nodo.nodo_id for nodo in nodos]
        latest_by_nodo = _latest_readings_by_nodos(db, nodo_ids, readings_limit)
        latest_last_seen = _latest_last_seen_by_nodos(db, nodo_ids)

        result = {
            "cama_id": cama.cama_id,
            "nombre": cama.nombre,
            "nodos": [
                {
                    "nodo_id": nodo.nodo_id,
                    "cama_id": nodo.cama_id,
                    "codigo_nodo": nodo.codigo_nodo,
                    "ultima_lectura_recibida": nodo.ultima_lectura_recibida or latest_last_seen.get(nodo.nodo_id),
                    "lecturas_actuales": latest_by_nodo.get(nodo.nodo_id, {}),
                }
                for nodo in nodos
            ],
        }
        logger.debug("Digital twin get_cama_twin_state completed cama_id=%s nodos=%s", cama_id, len(result["nodos"]))
        return result
    except (NotFoundError, ValidationError, PersistenceError):
        logger.warning("Digital twin get_cama_twin_state validation/notfound cama_id=%s", cama_id)
        raise
    except SQLAlchemyError as exc:
        logger.exception("Digital twin get_cama_twin_state failed cama_id=%s", cama_id)
        raise PersistenceError("error al consultar estado twin de cama") from exc


def get_all_camas_twin_state(db: Session, readings_limit: int = 200) -> list[dict]:
    logger.debug("Digital twin get_all_camas_twin_state start readings_limit=%s", readings_limit)
    try:
        _validate_limit(readings_limit)
        camas = db.query(CamaVermicompostaje).all()
        nodos = db.query(NodoSensor).all()

        nodos_by_cama: dict[int, list[NodoSensor]] = {}
        for nodo in nodos:
            nodos_by_cama.setdefault(nodo.cama_id, []).append(nodo)

        latest_by_nodo = _latest_readings_by_nodos(db, [nodo.nodo_id for nodo in nodos], readings_limit)
        latest_last_seen = _latest_last_seen_by_nodos(db, [nodo.nodo_id for nodo in nodos])

        result = []
        for cama in camas:
            cama_nodos = nodos_by_cama.get(cama.cama_id, [])
            result.append(
                {
                    "cama_id": cama.cama_id,
                    "nombre": cama.nombre,
                    "nodos": [
                        {
                            "nodo_id": nodo.nodo_id,
                            "cama_id": nodo.cama_id,
                            "codigo_nodo": nodo.codigo_nodo,
                            "ultima_lectura_recibida": nodo.ultima_lectura_recibida
                            or latest_last_seen.get(nodo.nodo_id),
                            "lecturas_actuales": latest_by_nodo.get(nodo.nodo_id, {}),
                        }
                        for nodo in cama_nodos
                    ],
                }
            )

        logger.debug("Digital twin get_all_camas_twin_state completed camas=%s", len(result))
        return result
    except (ValidationError, NotFoundError, PersistenceError):
        logger.warning("Digital twin get_all_camas_twin_state validation/persistence error")
        raise
    except SQLAlchemyError as exc:
        logger.exception("Digital twin get_all_camas_twin_state failed")
        raise PersistenceError("error al consultar estados twin") from exc


def get_twin_overview(db: Session) -> dict:
    logger.debug("Digital twin get_twin_overview start")
    try:
        lecturas_validas = db.query(func.count(Lectura.lectura_id)).scalar() or 0
        lecturas_invalidas = db.query(func.count(LecturaInvalida.lectura_invalida_id)).scalar() or 0
        result = {
            "total_camas": db.query(func.count(CamaVermicompostaje.cama_id)).scalar() or 0,
            "total_nodos": db.query(func.count(NodoSensor.nodo_id)).scalar() or 0,
            "lecturas_validas": lecturas_validas,
            "lecturas_invalidas": lecturas_invalidas,
        }
        logger.debug(
            "Digital twin get_twin_overview completed total_camas=%s total_nodos=%s lecturas_validas=%s lecturas_invalidas=%s",
            result["total_camas"],
            result["total_nodos"],
            result["lecturas_validas"],
            result["lecturas_invalidas"],
        )
        return result
    except SQLAlchemyError as exc:
        logger.exception("Digital twin get_twin_overview failed")
        raise PersistenceError("error al consultar overview twin") from exc
