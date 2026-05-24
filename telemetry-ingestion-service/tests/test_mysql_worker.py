import pathlib
import sys

import pytest

SERVICE_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.database.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import mysql_worker
from app.models.telemetry_model import TipoVariable


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


def test_resolve_tipo_variable_ids_with_retry_waits_until_success(monkeypatch):
    attempts = {"count": 0}

    def fake_resolver():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("no existe tipo_variable")
        return (1, 2, 3)

    class DummyStopEvent:
        def is_set(self):
            return False

        def wait(self, _seconds):
            return False

    monkeypatch.setattr(mysql_worker, "_resolve_tipo_variable_ids", fake_resolver)
    monkeypatch.setattr(mysql_worker, "_stop_event", DummyStopEvent())

    result = mysql_worker._resolve_tipo_variable_ids_with_retry()

    assert result == (1, 2, 3)
    assert attempts["count"] == 2


@pytest.mark.parametrize(
    ("nombre_legacy", "nombre_db", "expected"),
    [
        ("Temperatura ambiental", "Temperatura ambiental", 1),
        ("Temperatura ambiental", "Temperatura", 1),
        ("Temperatura ambiental", "temperatura", 1),
        ("Humedad relativa", "Humedad relativa", 2),
        ("Humedad relativa", "Humedad Relativa", 2),
        ("Humedad relativa", "humedad relativa", 2),
        ("Humedad relativa", "Humedad", 2),
        ("Humedad relativa", "humedad", 2),
        ("pH", "pH", 3),
        ("pH", "PH", 3),
        ("pH", "ph", 3),
    ],
)
def test_resolve_tipo_variable_id_accepts_aliases(db_session, nombre_legacy, nombre_db, expected):
    db_session.add(TipoVariable(tipo_variable_id=expected, nombre=nombre_db, unidad_medida="unit"))
    db_session.commit()

    result = mysql_worker._resolve_tipo_variable_id(db_session, nombre_legacy, configured_id=0)

    assert result == expected