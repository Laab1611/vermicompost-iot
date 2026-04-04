from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, DependencyError, NotFoundError, PersistenceError, ValidationError
from app.models.telemetry_model import CamaVermicompostaje, Lectura, LecturaInvalida, NodoSensor, TipoVariable
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

INGESTION_ERROR_TYPES = {
    "timestamp_invalido",
    "nodo_no_registrado",
    "tipo_variable_no_soportado",
    "payload_incompleto",
    "valor_fuera_de_rango",
    "error_desconocido",
}


def _now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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


def _is_blank(value: Any) -> bool:
    return isinstance(value, str) and not value.strip()


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


def _parse_int(value: Any) -> Optional[int]:
    if value is None or _is_blank(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _as_raw_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _resolve_existing_nodo_id(db: Session, nodo_id: Optional[int]) -> Optional[int]:
    if nodo_id is None:
        return None
    nodo = telemetry_repository.get_nodo(db, nodo_id)
    return nodo.nodo_id if nodo else None


def _resolve_existing_tipo_variable_id(db: Session, tipo_variable_id: Optional[int]) -> Optional[int]:
    if tipo_variable_id is None:
        return None
    tipo = telemetry_repository.get_tipo_variable(db, tipo_variable_id)
    return tipo.tipo_variable_id if tipo else None


def _persist_invalid_reading(
    db: Session,
    *,
    nodo_id: Optional[int],
    tipo_variable_id: Optional[int],
    valor_recibido: str,
    fecha_medicion: str,
    tipo_error: str,
) -> LecturaInvalida:
    if tipo_error not in INGESTION_ERROR_TYPES:
        tipo_error = "error_desconocido"

    lectura_invalida = LecturaInvalida(
        nodo_id=nodo_id,
        tipo_variable_id=tipo_variable_id,
        valor_recibido=valor_recibido,
        fecha_medicion=fecha_medicion,
        fecha_recepcion=datetime.now(UTC),
        tipo_error=tipo_error,
    )
    try:
        return telemetry_repository.create_lectura_invalida(db, lectura_invalida)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al registrar lectura invalida") from exc


def _invalid_ingestion_response(tipo_error: str) -> dict[str, Any]:
    return {
        "message": "Lectura invalida registrada",
        "lectura_id": None,
        "es_valida": False,
        "motivo_invalidacion": tipo_error,
        "persistida": True,
    }


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
    get_tipo_variable_or_fail(db, payload.tipo_variable_id)
    fecha_recepcion = payload.fecha_recepcion or datetime.now(UTC)
    _validate_reading_dates(payload.fecha_medicion, fecha_recepcion)

    lectura = Lectura(
        nodo_id=payload.nodo_id,
        tipo_variable_id=payload.tipo_variable_id,
        valor=payload.valor,
        fecha_medicion=payload.fecha_medicion,
        fecha_recepcion=fecha_recepcion,
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
    raw_nodo_id = data.get("nodo_id")
    raw_tipo_variable_id = data.get("tipo_variable_id")
    raw_valor = data.get("valor")
    raw_fecha_medicion = data.get("fecha_medicion")
    raw_fecha_recepcion = data.get("fecha_recepcion")

    nodo_id = _parse_int(raw_nodo_id)
    tipo_variable_id = _parse_int(raw_tipo_variable_id)
    valor = _parse_decimal(raw_valor)
    fecha_medicion = _parse_datetime(raw_fecha_medicion)
    fecha_recepcion = _parse_datetime(raw_fecha_recepcion) if raw_fecha_recepcion is not None else None

    valor_recibido = _as_raw_text(raw_valor)
    fecha_medicion_cruda = _as_raw_text(raw_fecha_medicion)

    try:
        invalid_non_decimal_value = raw_valor is not None and not _is_blank(raw_valor) and valor is None
        if invalid_non_decimal_value:
            _persist_invalid_reading(
                db,
                nodo_id=_resolve_existing_nodo_id(db, nodo_id),
                tipo_variable_id=_resolve_existing_tipo_variable_id(db, tipo_variable_id),
                valor_recibido=valor_recibido,
                fecha_medicion=fecha_medicion_cruda,
                tipo_error="valor_fuera_de_rango",
            )
            return _invalid_ingestion_response("valor_fuera_de_rango")

        missing_required = (
            raw_nodo_id is None
            or raw_tipo_variable_id is None
            or raw_valor is None
            or raw_fecha_medicion is None
            or _is_blank(raw_nodo_id)
            or _is_blank(raw_tipo_variable_id)
            or _is_blank(raw_valor)
            or _is_blank(raw_fecha_medicion)
            or nodo_id is None
            or tipo_variable_id is None
        )
        if missing_required:
            _persist_invalid_reading(
                db,
                nodo_id=_resolve_existing_nodo_id(db, nodo_id),
                tipo_variable_id=_resolve_existing_tipo_variable_id(db, tipo_variable_id),
                valor_recibido=valor_recibido,
                fecha_medicion=fecha_medicion_cruda,
                tipo_error="payload_incompleto",
            )
            return _invalid_ingestion_response("payload_incompleto")

        nodo = telemetry_repository.get_nodo(db, nodo_id)
        if not nodo:
            _persist_invalid_reading(
                db,
                nodo_id=None,
                tipo_variable_id=_resolve_existing_tipo_variable_id(db, tipo_variable_id),
                valor_recibido=valor_recibido,
                fecha_medicion=fecha_medicion_cruda,
                tipo_error="nodo_no_registrado",
            )
            return _invalid_ingestion_response("nodo_no_registrado")

        tipo = telemetry_repository.get_tipo_variable(db, tipo_variable_id)
        if not tipo:
            _persist_invalid_reading(
                db,
                nodo_id=nodo.nodo_id,
                tipo_variable_id=None,
                valor_recibido=valor_recibido,
                fecha_medicion=fecha_medicion_cruda,
                tipo_error="tipo_variable_no_soportado",
            )
            return _invalid_ingestion_response("tipo_variable_no_soportado")

        if fecha_medicion is None or (raw_fecha_recepcion is not None and fecha_recepcion is None):
            _persist_invalid_reading(
                db,
                nodo_id=nodo.nodo_id,
                tipo_variable_id=tipo.tipo_variable_id,
                valor_recibido=valor_recibido,
                fecha_medicion=fecha_medicion_cruda,
                tipo_error="timestamp_invalido",
            )
            return _invalid_ingestion_response("timestamp_invalido")

        effective_fecha_recepcion = fecha_recepcion or datetime.now(UTC)
        if _has_timestamp_issue(fecha_medicion, effective_fecha_recepcion):
            _persist_invalid_reading(
                db,
                nodo_id=nodo.nodo_id,
                tipo_variable_id=tipo.tipo_variable_id,
                valor_recibido=valor_recibido,
                fecha_medicion=fecha_medicion_cruda,
                tipo_error="timestamp_invalido",
            )
            return _invalid_ingestion_response("timestamp_invalido")

        lectura = Lectura(
            nodo_id=nodo.nodo_id,
            tipo_variable_id=tipo.tipo_variable_id,
            valor=valor,
            fecha_medicion=fecha_medicion,
            fecha_recepcion=effective_fecha_recepcion,
        )
        db.add(lectura)
        nodo.ultima_lectura_recibida = effective_fecha_recepcion
        db.commit()
        db.refresh(lectura)
        return {
            "message": "Lectura recibida",
            "lectura_id": lectura.lectura_id,
            "es_valida": True,
            "motivo_invalidacion": None,
            "persistida": True,
        }
    except PersistenceError:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise PersistenceError("error al registrar ingesta") from exc
    except Exception:
        db.rollback()
        _persist_invalid_reading(
            db,
            nodo_id=_resolve_existing_nodo_id(db, nodo_id),
            tipo_variable_id=_resolve_existing_tipo_variable_id(db, tipo_variable_id),
            valor_recibido=valor_recibido,
            fecha_medicion=fecha_medicion_cruda,
            tipo_error="error_desconocido",
        )
        return _invalid_ingestion_response("error_desconocido")


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
    get_tipo_variable_or_fail(db, payload.tipo_variable_id)
    fecha_recepcion = payload.fecha_recepcion or lectura.fecha_recepcion
    _validate_reading_dates(payload.fecha_medicion, fecha_recepcion)

    lectura.nodo_id = payload.nodo_id
    lectura.tipo_variable_id = payload.tipo_variable_id
    lectura.valor = payload.valor
    lectura.fecha_medicion = payload.fecha_medicion
    lectura.fecha_recepcion = fecha_recepcion
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
