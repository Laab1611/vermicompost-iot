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
from app.models.query_model import CamaVermicompostaje, Lectura, LecturaInvalida, NodoSensor, TipoVariable
from app.services import query_service


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

    cama1 = CamaVermicompostaje(nombre="Cama A", ubicacion="Zona A")
    cama2 = CamaVermicompostaje(nombre="Cama B", ubicacion="Zona B")
    db_session.add_all([cama1, cama2])
    db_session.flush()

    nodo1 = NodoSensor(cama_id=cama1.cama_id, codigo_nodo="NODO-001", ultima_lectura_recibida=now - timedelta(minutes=5))
    nodo2 = NodoSensor(cama_id=cama2.cama_id, codigo_nodo="NODO-002", ultima_lectura_recibida=now - timedelta(minutes=45))
    db_session.add_all([nodo1, nodo2])
    db_session.flush()

    tipo_temp = TipoVariable(nombre="Temperatura ambiental", unidad_medida="degC")
    tipo_hum = TipoVariable(nombre="Humedad relativa", unidad_medida="%")
    db_session.add_all([tipo_temp, tipo_hum])
    db_session.flush()

    lectura_temp_old = Lectura(
        nodo_id=nodo1.nodo_id,
        tipo_variable_id=tipo_temp.tipo_variable_id,
        valor=24.1,
        fecha_medicion=now - timedelta(minutes=30),
        fecha_recepcion=now - timedelta(minutes=30),
    )
    lectura_temp_new = Lectura(
        nodo_id=nodo1.nodo_id,
        tipo_variable_id=tipo_temp.tipo_variable_id,
        valor=25.6,
        fecha_medicion=now - timedelta(minutes=10),
        fecha_recepcion=now - timedelta(minutes=10),
    )
    lectura_hum = Lectura(
        nodo_id=nodo1.nodo_id,
        tipo_variable_id=tipo_hum.tipo_variable_id,
        valor=61.2,
        fecha_medicion=now - timedelta(minutes=8),
        fecha_recepcion=now - timedelta(minutes=8),
    )
    db_session.add_all([lectura_temp_old, lectura_temp_new, lectura_hum])

    invalida_1 = LecturaInvalida(
        nodo_id=nodo1.nodo_id,
        tipo_variable_id=tipo_temp.tipo_variable_id,
        valor_recibido="texto-no-decimal",
        fecha_medicion="2026-04-01T10:00:00Z",
        fecha_recepcion=now - timedelta(minutes=7),
        tipo_error="valor_fuera_de_rango",
    )
    invalida_2 = LecturaInvalida(
        nodo_id=None,
        tipo_variable_id=None,
        valor_recibido="",
        fecha_medicion="",
        fecha_recepcion=now - timedelta(minutes=6),
        tipo_error="payload_incompleto",
    )
    db_session.add_all([invalida_1, invalida_2])
    db_session.commit()

    return {
        "cama1_id": cama1.cama_id,
        "cama2_id": cama2.cama_id,
        "nodo1_id": nodo1.nodo_id,
        "nodo2_id": nodo2.nodo_id,
        "tipo_temp_id": tipo_temp.tipo_variable_id,
        "now": now,
    }


def test_get_lecturas_by_nodo_returns_valid_rows(db_session, seeded_data):
    rows = query_service.get_lecturas_by_nodo(db_session, seeded_data["nodo1_id"], limit=10)

    assert len(rows) == 3
    assert all(row[10] is True for row in rows)
    assert all(row[11] is None for row in rows)


def test_get_lecturas_by_nodo_not_found_raises(db_session):
    with pytest.raises(NotFoundError):
        query_service.get_lecturas_by_nodo(db_session, nodo_id=9999, limit=10)


def test_get_lecturas_by_rango_invalid_raises_validation(db_session, seeded_data):
    start = seeded_data["now"]
    end = seeded_data["now"] - timedelta(hours=1)

    with pytest.raises(ValidationError):
        query_service.get_lecturas_by_rango(db_session, start=start, end=end, limit=100)


def test_get_lecturas_invalidas_reads_lectura_invalida(db_session, seeded_data):
    rows = query_service.get_lecturas_invalidas(db_session, limit=10)

    assert len(rows) == 2
    assert all(row[10] is False for row in rows)
    reasons = {row[11] for row in rows}
    assert {"valor_fuera_de_rango", "payload_incompleto"}.issubset(reasons)


def test_get_estado_actual_por_nodo_returns_latest_per_type(db_session, seeded_data):
    estado = query_service.get_estado_actual_por_nodo(db_session, seeded_data["nodo1_id"], minutes=15)

    assert estado["conectado"] is True
    assert estado["lecturas_actuales"]["Temperatura ambiental"] == pytest.approx(25.6)
    assert estado["lecturas_actuales"]["Humedad relativa"] == pytest.approx(61.2)


def test_get_monitoring_summary_counts_disconnected_and_invalid(db_session, seeded_data):
    summary = query_service.get_monitoring_summary(db_session, disconnect_minutes=15)

    assert summary["total_camas"] == 2
    assert summary["total_nodos"] == 2
    assert summary["nodos_desconectados"] == 1
    assert summary["nodos_conectados"] == 1
    assert summary["lecturas_invalidas"] == 2


def test_get_latest_sensor_averages_by_cama_groups_domain_metrics(db_session, seeded_data):
    now = seeded_data["now"]
    tipo_ph = TipoVariable(nombre="pH", unidad_medida="pH")
    db_session.add(tipo_ph)
    db_session.flush()

    lectura_ph_nodo_1 = Lectura(
        nodo_id=seeded_data["nodo1_id"],
        tipo_variable_id=tipo_ph.tipo_variable_id,
        valor=6.8,
        fecha_medicion=now - timedelta(minutes=3),
        fecha_recepcion=now - timedelta(minutes=3),
    )
    lectura_ph_nodo_2 = Lectura(
        nodo_id=seeded_data["nodo2_id"],
        tipo_variable_id=tipo_ph.tipo_variable_id,
        valor=7.1,
        fecha_medicion=now - timedelta(minutes=2),
        fecha_recepcion=now - timedelta(minutes=2),
    )
    db_session.add_all([lectura_ph_nodo_1, lectura_ph_nodo_2])
    db_session.commit()

    rows = query_service.get_latest_sensor_averages_by_cama(db_session)
    by_cama = {row["cama_id"]: row for row in rows}

    cama_1 = by_cama[seeded_data["cama1_id"]]
    assert cama_1["temperatura"] == pytest.approx(25.6)
    assert cama_1["humedad"] == pytest.approx(61.2)
    assert cama_1["ph"] == pytest.approx(6.8)

    cama_2 = by_cama[seeded_data["cama2_id"]]
    assert cama_2["temperatura"] is None
    assert cama_2["humedad"] is None
    assert cama_2["ph"] == pytest.approx(7.1)
