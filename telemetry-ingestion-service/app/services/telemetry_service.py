from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, DependencyError, NotFoundError, PersistenceError, ValidationError
from app.models.telemetry_model import CamaVermicompostaje, Lectura, NodoSensor, TipoVariable
from app.repository import telemetry_repository
from app.schemas.telemetry_schema import (
    CamaCreate,
    CamaUpdate,
    IngestionCreate,
    LecturaCreate,
    LecturaUpdate,
    NodoCreate,
    NodoUpdate,
    TipoVariableCreate,
    TipoVariableUpdate,
)

ALLOWED_VARIABLE_UNITS = {
    "temperatura ambiental": "degc",
    "humedad relativa": "%",
    "ph": "ph",
}

ALLOWED_INVALIDATION_REASONS = {
    "timestamp_invalido",
    "nodo_no_registrado",
    "tipo_variable_no_soportado",
    "payload_incompleto",
}


def _now_utc_naive() -> datetime:
    return datetime.utcnow()


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _validate_reading_dates(fecha_medicion: datetime, fecha_recepcion: datetime) -> None:
    fm = _to_naive_utc(fecha_medicion)
    fr = _to_naive_utc(fecha_recepcion)
    now = _now_utc_naive()

    # Measurement cannot be in the future.
    if fm > now:
        raise ValidationError("fecha_medicion no puede ser futura")
    # Reception timestamp should be coherent with measurement.
    if fr < fm:
        raise ValidationError("fecha_recepcion no puede ser anterior a fecha_medicion")
    # Prevent far-future reception values from bad clients.
    if fr > now:
        raise ValidationError("fecha_recepcion no puede ser futura")


def _has_timestamp_issue(fecha_medicion: datetime, fecha_recepcion: datetime) -> bool:
    fm = _to_naive_utc(fecha_medicion)
    fr = _to_naive_utc(fecha_recepcion)
    now = _now_utc_naive()
    return fm > now or fr < fm or fr > now


def _normalize_unit(unit: str) -> str:
    normalized = unit.strip().lower().replace("°", "deg")
    return normalized


def _validate_variable_unit(nombre: str, unidad_medida: str) -> None:
    normalized_name = nombre.strip().lower()
    normalized_unit = _normalize_unit(unidad_medida)
    if normalized_name in ALLOWED_VARIABLE_UNITS:
        expected = ALLOWED_VARIABLE_UNITS[normalized_name]
        if normalized_unit != expected:
            raise ValidationError(f"unidad_medida invalida para {nombre}")


def _evaluate_reading_validity(tipo: TipoVariable, valor: Decimal) -> tuple[bool, Optional[str]]:
    # Range interpretation belongs to Grafana alerting configuration.
    # Backend persists any numeric value and does not invalidate by thresholds.
    _ = tipo
    _ = valor
    return True, None


def _coherent_validity(
    tipo: TipoVariable,
    valor: Decimal,
) -> tuple[bool, Optional[str]]:
    evaluated_valid, evaluated_reason = _evaluate_reading_validity(tipo, valor)
    return evaluated_valid, evaluated_reason


def _derive_ingestion_validity(tipo: TipoVariable, valor: Decimal, fecha_medicion: datetime, fecha_recepcion: datetime) -> tuple[bool, Optional[str]]:
    if _has_timestamp_issue(fecha_medicion, fecha_recepcion):
        return False, "timestamp_invalido"
    return _evaluate_reading_validity(tipo, valor)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            # Accept ISO timestamps including trailing Z.
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def create_cama(db: Session, payload: CamaCreate) -> CamaVermicompostaje:
    cama = CamaVermicompostaje(**payload.model_dump())
    return telemetry_repository.create_cama(db, cama)


def list_camas(db: Session) -> list[CamaVermicompostaje]:
    return telemetry_repository.list_camas(db)


def get_cama_or_fail(db: Session, cama_id: int) -> CamaVermicompostaje:
    cama = telemetry_repository.get_cama(db, cama_id)
    if not cama:
        raise NotFoundError("cama no encontrada")
    return cama


def update_cama(db: Session, cama_id: int, payload: CamaUpdate) -> CamaVermicompostaje:
    cama = get_cama_or_fail(db, cama_id)
    try:
        for key, value in payload.model_dump().items():
            setattr(cama, key, value)
        db.commit()
        db.refresh(cama)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al actualizar cama") from exc
    return cama


def delete_cama(db: Session, cama_id: int) -> None:
    get_cama_or_fail(db, cama_id)
    try:
        telemetry_repository.delete_cama_cascade(db, cama_id)
    except IntegrityError as exc:
        db.rollback()
        raise DependencyError("no se puede eliminar cama con registros relacionados") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al eliminar cama") from exc


def create_nodo(db: Session, payload: NodoCreate) -> NodoSensor:
    get_cama_or_fail(db, payload.cama_id)
    if telemetry_repository.get_nodo_by_codigo(db, payload.codigo_nodo):
        raise ConflictError("codigo_nodo ya existe")
    nodo = NodoSensor(**payload.model_dump(), created_at=_now_utc_naive())
    try:
        return telemetry_repository.create_nodo(db, nodo)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al crear nodo") from exc


def list_nodos(db: Session) -> list[NodoSensor]:
    return telemetry_repository.list_nodos(db)


def get_nodo_or_fail(db: Session, nodo_id: int) -> NodoSensor:
    nodo = telemetry_repository.get_nodo(db, nodo_id)
    if not nodo:
        raise NotFoundError("nodo no encontrado")
    return nodo


def update_nodo(db: Session, nodo_id: int, payload: NodoUpdate) -> NodoSensor:
    get_cama_or_fail(db, payload.cama_id)
    nodo = get_nodo_or_fail(db, nodo_id)
    existing = telemetry_repository.get_nodo_by_codigo(db, payload.codigo_nodo)
    if existing and existing.nodo_id != nodo_id:
        raise ConflictError("codigo_nodo ya existe")
    try:
        for key, value in payload.model_dump().items():
            setattr(nodo, key, value)
        db.commit()
        db.refresh(nodo)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al actualizar nodo") from exc
    return nodo


def delete_nodo(db: Session, nodo_id: int) -> None:
    get_nodo_or_fail(db, nodo_id)
    try:
        telemetry_repository.delete_nodo_cascade(db, nodo_id)
    except IntegrityError as exc:
        db.rollback()
        raise DependencyError("no se puede eliminar nodo con registros relacionados") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al eliminar nodo") from exc


def create_tipo_variable(db: Session, payload: TipoVariableCreate) -> TipoVariable:
    _validate_variable_unit(payload.nombre, payload.unidad_medida)
    if telemetry_repository.get_tipo_variable_by_nombre(db, payload.nombre):
        raise ConflictError("tipo_variable ya existe")
    tipo = TipoVariable(**payload.model_dump())
    try:
        return telemetry_repository.create_tipo_variable(db, tipo)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al crear tipo_variable") from exc


def list_tipos_variable(db: Session) -> list[TipoVariable]:
    return telemetry_repository.list_tipos_variable(db)


def get_tipo_variable_or_fail(db: Session, tipo_variable_id: int) -> TipoVariable:
    tipo = telemetry_repository.get_tipo_variable(db, tipo_variable_id)
    if not tipo:
        raise NotFoundError("tipo_variable no encontrado")
    return tipo


def update_tipo_variable(db: Session, tipo_variable_id: int, payload: TipoVariableUpdate) -> TipoVariable:
    _validate_variable_unit(payload.nombre, payload.unidad_medida)
    tipo = get_tipo_variable_or_fail(db, tipo_variable_id)
    existing = telemetry_repository.get_tipo_variable_by_nombre(db, payload.nombre)
    if existing and existing.tipo_variable_id != tipo_variable_id:
        raise ConflictError("tipo_variable ya existe")
    try:
        tipo.nombre = payload.nombre
        tipo.unidad_medida = payload.unidad_medida
        db.commit()
        db.refresh(tipo)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al actualizar tipo_variable") from exc
    return tipo


def delete_tipo_variable(db: Session, tipo_variable_id: int) -> None:
    tipo = get_tipo_variable_or_fail(db, tipo_variable_id)
    try:
        telemetry_repository.delete_tipo_variable(db, tipo)
    except IntegrityError as exc:
        db.rollback()
        raise DependencyError("no se puede eliminar tipo_variable con registros relacionados") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al eliminar tipo_variable") from exc


def create_lectura(db: Session, payload: LecturaCreate) -> Lectura:
    nodo = get_nodo_or_fail(db, payload.nodo_id)
    tipo = get_tipo_variable_or_fail(db, payload.tipo_variable_id)
    final_valid, final_reason = _coherent_validity(tipo, payload.valor)
    fecha_recepcion = payload.fecha_recepcion or datetime.now(UTC)
    _validate_reading_dates(payload.fecha_medicion, fecha_recepcion)

    lectura = Lectura(
        nodo_id=payload.nodo_id,
        tipo_variable_id=payload.tipo_variable_id,
        valor=payload.valor,
        fecha_medicion=payload.fecha_medicion,
        fecha_recepcion=fecha_recepcion,
        es_valida=final_valid,
        motivo_invalidacion=final_reason,
    )
    try:
        db.add(lectura)
        nodo.ultima_lectura_recibida = fecha_recepcion
        db.commit()
        db.refresh(lectura)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al crear lectura") from exc
    return lectura


def ingest_telemetry(db: Session, payload: IngestionCreate | dict[str, Any]) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else payload.model_dump()

    nodo_id = data.get("nodo_id")
    tipo_variable_id = data.get("tipo_variable_id")
    valor = _parse_decimal(data.get("valor"))
    fecha_medicion = _parse_datetime(data.get("fecha_medicion"))
    fecha_recepcion = _parse_datetime(data.get("fecha_recepcion")) or datetime.now(UTC)

    # Accept request and classify as invalid when payload is incomplete/unparseable.
    if nodo_id is None or tipo_variable_id is None or valor is None or fecha_medicion is None:
        return {
            "message": "Lectura recibida con inconsistencias",
            "lectura_id": None,
            "es_valida": False,
            "motivo_invalidacion": "payload_incompleto",
            "persistida": False,
        }

    nodo = telemetry_repository.get_nodo(db, int(nodo_id))
    if not nodo:
        return {
            "message": "Lectura recibida con inconsistencias",
            "lectura_id": None,
            "es_valida": False,
            "motivo_invalidacion": "nodo_no_registrado",
            "persistida": False,
        }

    tipo = telemetry_repository.get_tipo_variable(db, int(tipo_variable_id))
    if not tipo:
        return {
            "message": "Lectura recibida con inconsistencias",
            "lectura_id": None,
            "es_valida": False,
            "motivo_invalidacion": "tipo_variable_no_soportado",
            "persistida": False,
        }

    final_valid, final_reason = _derive_ingestion_validity(tipo, valor, fecha_medicion, fecha_recepcion)

    lectura = Lectura(
        nodo_id=int(nodo_id),
        tipo_variable_id=int(tipo_variable_id),
        valor=valor,
        fecha_medicion=fecha_medicion,
        fecha_recepcion=fecha_recepcion,
        es_valida=final_valid,
        motivo_invalidacion=final_reason,
    )
    try:
        db.add(lectura)
        nodo.ultima_lectura_recibida = fecha_recepcion
        db.commit()
        db.refresh(lectura)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al registrar ingesta") from exc

    return {
        "message": "Lectura recibida",
        "lectura_id": lectura.lectura_id,
        "es_valida": lectura.es_valida,
        "motivo_invalidacion": lectura.motivo_invalidacion,
        "persistida": True,
    }


def list_lecturas(db: Session) -> list[Lectura]:
    return telemetry_repository.list_lecturas(db)


def get_lectura_or_fail(db: Session, lectura_id: int) -> Lectura:
    lectura = telemetry_repository.get_lectura(db, lectura_id)
    if not lectura:
        raise NotFoundError("lectura no encontrada")
    return lectura


def update_lectura(db: Session, lectura_id: int, payload: LecturaUpdate) -> Lectura:
    lectura = get_lectura_or_fail(db, lectura_id)
    nodo = get_nodo_or_fail(db, payload.nodo_id)
    tipo = get_tipo_variable_or_fail(db, payload.tipo_variable_id)
    final_valid, final_reason = _coherent_validity(tipo, payload.valor)
    fecha_recepcion = payload.fecha_recepcion or lectura.fecha_recepcion
    _validate_reading_dates(payload.fecha_medicion, fecha_recepcion)

    lectura.nodo_id = payload.nodo_id
    lectura.tipo_variable_id = payload.tipo_variable_id
    lectura.valor = payload.valor
    lectura.fecha_medicion = payload.fecha_medicion
    lectura.fecha_recepcion = fecha_recepcion
    lectura.es_valida = final_valid
    lectura.motivo_invalidacion = final_reason
    nodo.ultima_lectura_recibida = fecha_recepcion

    try:
        db.commit()
        db.refresh(lectura)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al actualizar lectura") from exc
    return lectura


def delete_lectura(db: Session, lectura_id: int) -> None:
    lectura = get_lectura_or_fail(db, lectura_id)
    try:
        telemetry_repository.delete_lectura(db, lectura)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al eliminar lectura") from exc
