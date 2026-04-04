from datetime import UTC, datetime, timedelta
import pathlib
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SERVICE_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.database.base import Base
from app.exceptions import NotFoundError, ValidationError
from app.models.digital_model import CamaVermicompostaje, Lectura, LecturaInvalida, NodoSensor, TipoVariable
from app.services import digital_service


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
def seeded_data(db_session):
    now = datetime.now(UTC)

    cama = CamaVermicompostaje(nombre="Cama Twin", ubicacion="Invernadero")
    db_session.add(cama)
    db_session.flush()

    nodo = NodoSensor(cama_id=cama.cama_id, codigo_nodo="NODO-TWIN-1", ultima_lectura_recibida=now - timedelta(minutes=3))
    db_session.add(nodo)
    db_session.flush()

    tipo_temp = TipoVariable(nombre="Temperatura ambiental", unidad_medida="degC")
    tipo_ph = TipoVariable(nombre="pH", unidad_medida="pH")
    db_session.add_all([tipo_temp, tipo_ph])
    db_session.flush()

    lectura_temp_old = Lectura(
        nodo_id=nodo.nodo_id,
        tipo_variable_id=tipo_temp.tipo_variable_id,
        valor=23.5,
        fecha_medicion=now - timedelta(minutes=25),
        fecha_recepcion=now - timedelta(minutes=25),
    )
    lectura_temp_new = Lectura(
        nodo_id=nodo.nodo_id,
        tipo_variable_id=tipo_temp.tipo_variable_id,
        valor=24.2,
        fecha_medicion=now - timedelta(minutes=4),
        fecha_recepcion=now - timedelta(minutes=4),
    )
    lectura_ph = Lectura(
        nodo_id=nodo.nodo_id,
        tipo_variable_id=tipo_ph.tipo_variable_id,
        valor=6.8,
        fecha_medicion=now - timedelta(minutes=5),
        fecha_recepcion=now - timedelta(minutes=5),
    )
    db_session.add_all([lectura_temp_old, lectura_temp_new, lectura_ph])

    invalida = LecturaInvalida(
        nodo_id=nodo.nodo_id,
        tipo_variable_id=tipo_temp.tipo_variable_id,
        valor_recibido="texto",
        fecha_medicion="2026-04-01T10:00:00Z",
        fecha_recepcion=now - timedelta(minutes=2),
        tipo_error="valor_fuera_de_rango",
    )
    db_session.add(invalida)
    db_session.commit()

    return {"cama_id": cama.cama_id, "nodo_id": nodo.nodo_id}


def test_get_nodo_twin_state_returns_latest_readings(db_session, seeded_data):
    state = digital_service.get_nodo_twin_state(db_session, seeded_data["nodo_id"], readings_limit=200)

    assert state["nodo_id"] == seeded_data["nodo_id"]
    assert state["lecturas_actuales"]["Temperatura ambiental"] == pytest.approx(24.2)
    assert state["lecturas_actuales"]["pH"] == pytest.approx(6.8)


def test_get_cama_twin_state_not_found_raises(db_session):
    with pytest.raises(NotFoundError):
        digital_service.get_cama_twin_state(db_session, cama_id=9999, readings_limit=200)


def test_get_all_camas_twin_state_invalid_limit_raises(db_session, seeded_data):
    with pytest.raises(ValidationError):
        digital_service.get_all_camas_twin_state(db_session, readings_limit=0)


def test_get_twin_overview_counts_valid_and_invalid(db_session, seeded_data):
    overview = digital_service.get_twin_overview(db_session)

    assert overview["total_camas"] == 1
    assert overview["total_nodos"] == 1
    assert overview["lecturas_validas"] == 3
    assert overview["lecturas_invalidas"] == 1


def test_get_all_camas_twin_state_success(db_session, seeded_data):
    all_states = digital_service.get_all_camas_twin_state(db_session, readings_limit=200)

    assert len(all_states) == 1
    assert all_states[0]["cama_id"] == seeded_data["cama_id"]
    assert len(all_states[0]["nodos"]) == 1
