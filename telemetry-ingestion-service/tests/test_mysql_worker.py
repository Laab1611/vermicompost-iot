import pathlib
import sys

SERVICE_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app import mysql_worker


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