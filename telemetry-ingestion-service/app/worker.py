from datetime import datetime
import logging
import signal
import threading

from app.broker.runtime import initialize_runtime, shutdown_runtime
from app.database.connection import SessionLocal
from app.repository import telemetry_repository
from app.services import telemetry_service

logger = logging.getLogger(__name__)

_stop_event = threading.Event()


def _process_ingestion_payload(payload: dict) -> dict:
    db = SessionLocal()
    try:
        return telemetry_service.prepare_ingestion_for_batch(db, payload)
    except Exception:
        logger.exception("Error processing broker payload")
        raise
    finally:
        db.close()


def _flush_ingestion_batch(rows: list[dict], last_seen_by_nodo: dict[int, datetime]) -> int:
    if not rows:
        return 0

    db = SessionLocal()
    try:
        inserted = telemetry_repository.bulk_create_lecturas(db, rows)
        telemetry_repository.bulk_update_nodo_last_seen(db, last_seen_by_nodo)
        db.commit()
        return inserted
    except Exception:
        db.rollback()
        logger.exception("Error flushing ingestion batch")
        raise
    finally:
        db.close()


def _handle_signal(signum, _frame) -> None:
    logger.info("Received signal %s, stopping worker", signum)
    _stop_event.set()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    initialize_runtime(_process_ingestion_payload, _flush_ingestion_batch)
    logger.info("Telemetry ingestion worker started")
    try:
        while not _stop_event.wait(0.5):
            pass
    finally:
        shutdown_runtime()
        logger.info("Telemetry ingestion worker stopped")


if __name__ == "__main__":
    main()