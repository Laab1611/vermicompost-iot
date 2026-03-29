from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, PersistenceError, ValidationError
from app.models.digital_model import CamaVermicompostaje, Lectura, NodoSensor, TipoVariable

MAX_QUERY_LIMIT = 1000


def _validate_limit(limit: int) -> None:
    if limit < 1 or limit > MAX_QUERY_LIMIT:
        raise ValidationError(f"limit debe estar entre 1 y {MAX_QUERY_LIMIT}")


def _latest_readings_by_nodo(db: Session, nodo_id: int, limit: int = 200) -> dict[str, float]:
    _validate_limit(limit)
    try:
        rows = (
            db.query(Lectura, TipoVariable)
            .join(TipoVariable, TipoVariable.tipo_variable_id == Lectura.tipo_variable_id)
            .filter(Lectura.nodo_id == nodo_id)
            .order_by(TipoVariable.tipo_variable_id.asc(), Lectura.fecha_recepcion.desc())
            .limit(limit)
            .all()
        )
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar lecturas del nodo") from exc
    result: dict[str, float] = {}
    for lectura, tipo in rows:
        if tipo.nombre not in result:
            result[tipo.nombre] = float(lectura.valor)
    return result


def get_nodo_twin_state(db: Session, nodo_id: int, readings_limit: int = 200) -> dict:
    try:
        nodo = db.query(NodoSensor).filter(NodoSensor.nodo_id == nodo_id).first()
        if not nodo:
            raise NotFoundError("nodo no encontrado")
        return {
            "nodo_id": nodo.nodo_id,
            "cama_id": nodo.cama_id,
            "codigo_nodo": nodo.codigo_nodo,
            "ultima_lectura_recibida": nodo.ultima_lectura_recibida,
            "lecturas_actuales": _latest_readings_by_nodo(db, nodo_id, readings_limit),
        }
    except (NotFoundError, ValidationError, PersistenceError):
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar estado twin de nodo") from exc


def get_cama_twin_state(db: Session, cama_id: int, readings_limit: int = 200) -> dict:
    try:
        cama = db.query(CamaVermicompostaje).filter(CamaVermicompostaje.cama_id == cama_id).first()
        if not cama:
            raise NotFoundError("cama no encontrada")
        nodos = db.query(NodoSensor).filter(NodoSensor.cama_id == cama_id).all()
        return {
            "cama_id": cama.cama_id,
            "nombre": cama.nombre,
            "nodos": [get_nodo_twin_state(db, nodo.nodo_id, readings_limit) for nodo in nodos],
        }
    except (NotFoundError, ValidationError, PersistenceError):
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar estado twin de cama") from exc


def get_all_camas_twin_state(db: Session, readings_limit: int = 200) -> list[dict]:
    try:
        _validate_limit(readings_limit)
        camas = db.query(CamaVermicompostaje).all()
        return [get_cama_twin_state(db, cama.cama_id, readings_limit) for cama in camas]
    except (ValidationError, NotFoundError, PersistenceError):
        raise
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar estados twin") from exc


def get_twin_overview(db: Session) -> dict:
    try:
        return {
            "total_camas": db.query(func.count(CamaVermicompostaje.cama_id)).scalar() or 0,
            "total_nodos": db.query(func.count(NodoSensor.nodo_id)).scalar() or 0,
            "lecturas_validas": db.query(func.count(Lectura.lectura_id)).filter(Lectura.es_valida.is_(True)).scalar() or 0,
            "lecturas_invalidas": db.query(func.count(Lectura.lectura_id)).filter(Lectura.es_valida.is_(False)).scalar() or 0,
        }
    except SQLAlchemyError as exc:
        raise PersistenceError("error al consultar overview twin") from exc
