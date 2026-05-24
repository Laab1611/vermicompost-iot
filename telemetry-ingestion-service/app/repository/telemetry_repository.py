from datetime import datetime
from typing import Any
from typing import Optional

from sqlalchemy.orm import Session

from app.models.telemetry_model import CamaVermicompostaje, Lectura, LecturaInvalida, NodoSensor, TipoVariable


def create_cama(db: Session, cama: CamaVermicompostaje) -> CamaVermicompostaje:
	db.add(cama)
	db.commit()
	db.refresh(cama)
	return cama


def list_camas(db: Session) -> list[CamaVermicompostaje]:
	return db.query(CamaVermicompostaje).order_by(CamaVermicompostaje.cama_id.asc()).all()


def get_cama(db: Session, cama_id: int) -> Optional[CamaVermicompostaje]:
	return db.query(CamaVermicompostaje).filter(CamaVermicompostaje.cama_id == cama_id).first()


def get_cama_by_values(
	db: Session,
	*,
	nombre: str,
	ubicacion: str,
	latitud: Optional[Any],
	longitud: Optional[Any],
) -> Optional[CamaVermicompostaje]:
	query = db.query(CamaVermicompostaje).filter(
		CamaVermicompostaje.nombre == nombre,
		CamaVermicompostaje.ubicacion == ubicacion,
	)
	if latitud is None:
		query = query.filter(CamaVermicompostaje.latitud.is_(None))
	else:
		query = query.filter(CamaVermicompostaje.latitud == latitud)
	if longitud is None:
		query = query.filter(CamaVermicompostaje.longitud.is_(None))
	else:
		query = query.filter(CamaVermicompostaje.longitud == longitud)
	return query.first()


def delete_cama(db: Session, cama: CamaVermicompostaje) -> None:
	db.delete(cama)
	db.commit()


def delete_cama_cascade(db: Session, cama_id: int) -> int:
	"""Delete a bed and all dependent nodes/readings in one transaction.

	Returns number of deleted nodes.
	"""
	nodos = db.query(NodoSensor).filter(NodoSensor.cama_id == cama_id).all()
	nodo_ids = [n.nodo_id for n in nodos]
	if nodo_ids:
		db.query(Lectura).filter(Lectura.nodo_id.in_(nodo_ids)).delete(synchronize_session=False)
		db.query(NodoSensor).filter(NodoSensor.cama_id == cama_id).delete(synchronize_session=False)
	db.query(CamaVermicompostaje).filter(CamaVermicompostaje.cama_id == cama_id).delete(synchronize_session=False)
	db.commit()
	return len(nodo_ids)


def create_nodo(db: Session, nodo: NodoSensor) -> NodoSensor:
	db.add(nodo)
	db.commit()
	db.refresh(nodo)
	return nodo


def list_nodos(db: Session) -> list[NodoSensor]:
	return db.query(NodoSensor).order_by(NodoSensor.nodo_id.asc()).all()


def get_nodo(db: Session, nodo_id: int) -> Optional[NodoSensor]:
	return db.query(NodoSensor).filter(NodoSensor.nodo_id == nodo_id).first()


def get_nodo_by_codigo(db: Session, codigo_nodo: str) -> Optional[NodoSensor]:
	return db.query(NodoSensor).filter(NodoSensor.codigo_nodo == codigo_nodo).first()


def delete_nodo(db: Session, nodo: NodoSensor) -> None:
	db.delete(nodo)
	db.commit()


def delete_nodo_cascade(db: Session, nodo_id: int) -> None:
	db.query(Lectura).filter(Lectura.nodo_id == nodo_id).delete(synchronize_session=False)
	db.query(NodoSensor).filter(NodoSensor.nodo_id == nodo_id).delete(synchronize_session=False)
	db.commit()


def create_tipo_variable(db: Session, tipo: TipoVariable) -> TipoVariable:
	db.add(tipo)
	db.commit()
	db.refresh(tipo)
	return tipo


def list_tipos_variable(db: Session) -> list[TipoVariable]:
	return db.query(TipoVariable).order_by(TipoVariable.tipo_variable_id.asc()).all()


def get_tipo_variable(db: Session, tipo_variable_id: int) -> Optional[TipoVariable]:
	return db.query(TipoVariable).filter(TipoVariable.tipo_variable_id == tipo_variable_id).first()


def get_tipo_variable_by_nombre(db: Session, nombre: str) -> Optional[TipoVariable]:
	return db.query(TipoVariable).filter(TipoVariable.nombre == nombre).first()


def delete_tipo_variable(db: Session, tipo: TipoVariable) -> None:
	db.delete(tipo)
	db.commit()


def create_lectura(db: Session, lectura: Lectura) -> Lectura:
	db.add(lectura)
	db.commit()
	db.refresh(lectura)
	return lectura


def create_lectura_invalida(db: Session, lectura_invalida: LecturaInvalida) -> LecturaInvalida:
	db.add(lectura_invalida)
	db.commit()
	db.refresh(lectura_invalida)
	return lectura_invalida


def list_lecturas(db: Session) -> list[Lectura]:
	return db.query(Lectura).order_by(Lectura.fecha_recepcion.desc()).all()


def get_lectura(db: Session, lectura_id: int) -> Optional[Lectura]:
	return db.query(Lectura).filter(Lectura.lectura_id == lectura_id).first()


def delete_lectura(db: Session, lectura: Lectura) -> None:
	db.delete(lectura)
	db.commit()


def update_ultima_lectura_nodo(db: Session, nodo: NodoSensor, when: datetime) -> None:
	nodo.ultima_lectura_recibida = when


def bulk_create_lecturas(db: Session, lecturas_rows: list[dict[str, Any]]) -> int:
	if not lecturas_rows:
		return 0
	db.bulk_insert_mappings(Lectura, lecturas_rows)
	return len(lecturas_rows)


def bulk_update_nodo_last_seen(db: Session, last_seen_by_nodo: dict[int, datetime]) -> None:
	for nodo_id, when in last_seen_by_nodo.items():
		db.query(NodoSensor).filter(NodoSensor.nodo_id == nodo_id).update(
			{NodoSensor.ultima_lectura_recibida: when},
			synchronize_session=False,
		)
