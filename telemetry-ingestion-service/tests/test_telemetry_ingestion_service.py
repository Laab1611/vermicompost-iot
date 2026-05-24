from datetime import UTC, datetime, timedelta
import pathlib
import sys

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SERVICE_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.database.base import Base
from app.exceptions import ConflictError, DependencyError, ValidationError
from app.models.telemetry_model import CamaVermicompostaje, Lectura, LecturaInvalida, NodoSensor, TipoVariable
from app.schemas.telemetry_schema import CamaCreate, CamaUpdate, LecturaCreate, NodoCreate
from app.services import telemetry_service


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def seeded_entities(db_session):
    cama = CamaVermicompostaje(nombre="Cama 1", ubicacion="Zona Norte")
    db_session.add(cama)
    db_session.flush()

    nodo = NodoSensor(cama_id=cama.cama_id, codigo_nodo="NODO-001")
    tipo = TipoVariable(nombre="Temperatura ambiental", unidad_medida="degC")
    db_session.add_all([nodo, tipo])
    db_session.commit()
    db_session.refresh(nodo)
    db_session.refresh(tipo)

    return {
        "cama_id": cama.cama_id,
        "nodo_id": nodo.nodo_id,
        "tipo_variable_id": tipo.tipo_variable_id,
    }


def _iso_utc(minutes_ago: int = 5) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()


def test_ingest_valid_payload_persists_lectura(db_session, seeded_entities):
    payload = {
        "nodo_id": seeded_entities["nodo_id"],
        "tipo_variable_id": seeded_entities["tipo_variable_id"],
        "valor": "27.8",
        "fecha_medicion": _iso_utc(10),
    }

    result = telemetry_service.ingest_telemetry(db_session, payload)

    assert result["persistida"] is True
    assert result["es_valida"] is True
    assert result["motivo_invalidacion"] is None
    assert result["lectura_id"] is not None
    assert db_session.query(Lectura).count() == 1
    assert db_session.query(LecturaInvalida).count() == 0


def test_ingest_numeric_outlier_is_still_valid(db_session, seeded_entities):
    payload = {
        "nodo_id": seeded_entities["nodo_id"],
        "tipo_variable_id": seeded_entities["tipo_variable_id"],
        "valor": "9999.99",
        "fecha_medicion": _iso_utc(8),
    }

    result = telemetry_service.ingest_telemetry(db_session, payload)

    assert result["es_valida"] is True
    assert result["motivo_invalidacion"] is None
    assert db_session.query(Lectura).count() == 1
    assert db_session.query(LecturaInvalida).count() == 0


def test_ingest_non_decimal_value_is_valor_fuera_de_rango(db_session, seeded_entities):
    payload = {
        "nodo_id": seeded_entities["nodo_id"],
        "tipo_variable_id": seeded_entities["tipo_variable_id"],
        "valor": "texto-no-decimal",
        "fecha_medicion": _iso_utc(7),
    }

    result = telemetry_service.ingest_telemetry(db_session, payload)

    assert result["persistida"] is True
    assert result["es_valida"] is False
    assert result["motivo_invalidacion"] == "valor_fuera_de_rango"
    assert db_session.query(Lectura).count() == 0

    invalid = db_session.query(LecturaInvalida).one()
    assert invalid.tipo_error == "valor_fuera_de_rango"
    assert invalid.valor_recibido == "texto-no-decimal"
    assert invalid.nodo_id == seeded_entities["nodo_id"]
    assert invalid.tipo_variable_id == seeded_entities["tipo_variable_id"]


def test_ingest_payload_incompleto_is_persisted(db_session, seeded_entities):
    payload = {"nodo_id": seeded_entities["nodo_id"]}

    result = telemetry_service.ingest_telemetry(db_session, payload)

    assert result["es_valida"] is False
    assert result["motivo_invalidacion"] == "payload_incompleto"
    invalid = db_session.query(LecturaInvalida).one()
    assert invalid.tipo_error == "payload_incompleto"
    assert invalid.nodo_id == seeded_entities["nodo_id"]
    assert invalid.tipo_variable_id is None


def test_ingest_unknown_node_sets_null_node_fk(db_session, seeded_entities):
    payload = {
        "nodo_id": 9999,
        "tipo_variable_id": seeded_entities["tipo_variable_id"],
        "valor": "27.1",
        "fecha_medicion": _iso_utc(6),
    }

    result = telemetry_service.ingest_telemetry(db_session, payload)

    assert result["motivo_invalidacion"] == "nodo_no_registrado"
    invalid = db_session.query(LecturaInvalida).one()
    assert invalid.tipo_error == "nodo_no_registrado"
    assert invalid.nodo_id is None
    assert invalid.tipo_variable_id == seeded_entities["tipo_variable_id"]


def test_ingest_unknown_tipo_sets_null_tipo_fk(db_session, seeded_entities):
    payload = {
        "nodo_id": seeded_entities["nodo_id"],
        "tipo_variable_id": 9999,
        "valor": "27.1",
        "fecha_medicion": _iso_utc(6),
    }

    result = telemetry_service.ingest_telemetry(db_session, payload)

    assert result["motivo_invalidacion"] == "tipo_variable_no_soportado"
    invalid = db_session.query(LecturaInvalida).one()
    assert invalid.tipo_error == "tipo_variable_no_soportado"
    assert invalid.nodo_id == seeded_entities["nodo_id"]
    assert invalid.tipo_variable_id is None


def test_ingest_future_measurement_is_timestamp_invalido(db_session, seeded_entities):
    payload = {
        "nodo_id": seeded_entities["nodo_id"],
        "tipo_variable_id": seeded_entities["tipo_variable_id"],
        "valor": "24.3",
        "fecha_medicion": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    }

    result = telemetry_service.ingest_telemetry(db_session, payload)

    assert result["motivo_invalidacion"] == "timestamp_invalido"
    invalid = db_session.query(LecturaInvalida).one()
    assert invalid.tipo_error == "timestamp_invalido"


def test_create_cama_rejects_duplicate_payload(db_session):
    payload = CamaCreate(nombre="Cama 1", ubicacion="Zona Norte")

    first = telemetry_service.create_cama(db_session, payload)

    with pytest.raises(ConflictError):
        telemetry_service.create_cama(db_session, payload)

    assert first.cama_id is not None
    assert db_session.query(CamaVermicompostaje).count() == 1


def test_update_cama_rejects_duplicate_payload(db_session):
    cama_a = telemetry_service.create_cama(db_session, CamaCreate(nombre="Cama A", ubicacion="Zona Norte"))
    cama_b = telemetry_service.create_cama(db_session, CamaCreate(nombre="Cama B", ubicacion="Zona Sur"))

    with pytest.raises(ConflictError):
        telemetry_service.update_cama(
            db_session,
            cama_b.cama_id,
            CamaUpdate(nombre=cama_a.nombre, ubicacion=cama_a.ubicacion, latitud=cama_a.latitud, longitud=cama_a.longitud),
        )

    assert db_session.query(CamaVermicompostaje).count() == 2


def test_create_nodo_rejects_duplicate_codigo(db_session, seeded_entities):
    payload = NodoCreate(cama_id=seeded_entities["cama_id"], codigo_nodo="NODO-001")

    with pytest.raises(ConflictError):
        telemetry_service.create_nodo(db_session, payload)

    assert db_session.query(NodoSensor).count() == 1


def test_delete_cama_blocks_when_it_has_nodes(db_session, seeded_entities):
    with pytest.raises(DependencyError):
        telemetry_service.delete_cama(db_session, seeded_entities["cama_id"])

    assert db_session.query(CamaVermicompostaje).count() == 1
    assert db_session.query(NodoSensor).count() == 1


def test_delete_cama_allows_empty_cama(db_session):
    cama = telemetry_service.create_cama(db_session, CamaCreate(nombre="Cama Vacia", ubicacion="Zona Este"))

    telemetry_service.delete_cama(db_session, cama.cama_id)

    assert db_session.query(CamaVermicompostaje).count() == 0


def test_delete_nodo_blocks_when_it_has_readings(db_session, seeded_entities):
    payload = LecturaCreate(
        nodo_id=seeded_entities["nodo_id"],
        tipo_variable_id=seeded_entities["tipo_variable_id"],
        valor=Decimal("25.5"),
        fecha_medicion=datetime.now(UTC) - timedelta(minutes=1),
        fecha_recepcion=datetime.now(UTC),
    )
    telemetry_service.create_lectura(db_session, payload)

    with pytest.raises(DependencyError):
        telemetry_service.delete_nodo(db_session, seeded_entities["nodo_id"])

    assert db_session.query(NodoSensor).count() == 1
    assert db_session.query(Lectura).count() == 1


def test_delete_nodo_allows_empty_nodo(db_session):
    cama = telemetry_service.create_cama(db_session, CamaCreate(nombre="Cama 2", ubicacion="Zona Sur"))
    nodo = telemetry_service.create_nodo(db_session, NodoCreate(cama_id=cama.cama_id, codigo_nodo="NODO-002"))

    telemetry_service.delete_nodo(db_session, nodo.nodo_id)

    assert db_session.query(NodoSensor).count() == 0


def test_ingest_reception_before_measurement_is_timestamp_invalido(db_session, seeded_entities):
    fecha_medicion = datetime.now(UTC) - timedelta(minutes=2)
    fecha_recepcion = fecha_medicion - timedelta(minutes=3)
    payload = {
        "nodo_id": seeded_entities["nodo_id"],
        "tipo_variable_id": seeded_entities["tipo_variable_id"],
        "valor": "24.3",
        "fecha_medicion": fecha_medicion.isoformat(),
        "fecha_recepcion": fecha_recepcion.isoformat(),
    }

    result = telemetry_service.ingest_telemetry(db_session, payload)

    assert result["motivo_invalidacion"] == "timestamp_invalido"
    invalid = db_session.query(LecturaInvalida).one()
    assert invalid.tipo_error == "timestamp_invalido"


def test_create_lectura_rejects_future_measurement(db_session, seeded_entities):
    payload = LecturaCreate(
        nodo_id=seeded_entities["nodo_id"],
        tipo_variable_id=seeded_entities["tipo_variable_id"],
        valor="25.0",
        fecha_medicion=datetime.now(UTC) + timedelta(minutes=10),
        fecha_recepcion=datetime.now(UTC),
    )

    with pytest.raises(ValidationError):
        telemetry_service.create_lectura(db_session, payload)

    assert db_session.query(Lectura).count() == 0
