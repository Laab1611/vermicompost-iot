from contextlib import asynccontextmanager
from datetime import datetime
import logging
import os
import time
import uuid

from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import router
from app.broker.runtime import initialize_runtime, shutdown_runtime
from app.database.connection import SessionLocal
from app.repository import telemetry_repository
from app.services import telemetry_service

logger = logging.getLogger(__name__)
NOISY_PATHS = {"/health", "/metrics"}
SLOW_REQUEST_WARN_MS = float(os.getenv("SLOW_REQUEST_WARN_MS", "5000"))


def _setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting telemetry-ingestion-service")
    initialize_runtime(_process_ingestion_payload, _flush_ingestion_batch)
    yield
    logger.info("Stopping telemetry-ingestion-service")
    shutdown_runtime()


_setup_logging()
app = FastAPI(title="Telemetry Ingestion Service", lifespan=lifespan)


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    path = request.url.path
    is_mutation = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "HTTP request failed: id=%s method=%s path=%s duration_ms=%.2f",
            request_id,
            request.method,
            path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-Id"] = request_id
    if path not in NOISY_PATHS:
        if is_mutation or response.status_code >= 400:
            logger.info(
                "HTTP request completed: id=%s method=%s path=%s status=%s duration_ms=%.2f",
                request_id,
                request.method,
                path,
                response.status_code,
                duration_ms,
            )
        elif duration_ms >= SLOW_REQUEST_WARN_MS:
            logger.warning(
                "Slow HTTP request: id=%s method=%s path=%s status=%s duration_ms=%.2f",
                request_id,
                request.method,
                path,
                response.status_code,
                duration_ms,
            )
    return response

Instrumentator().instrument(app).expose(app)
app.include_router(router)