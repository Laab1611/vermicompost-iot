from contextlib import asynccontextmanager
import logging
import os
import threading
import time
import uuid

from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import router
from app.config import settings
from app.database.connection import SessionLocal
from app.metrics.prometheus import (
	update_cama_info_metrics,
	update_errores_por_nodo_metrics,
	update_invalidaciones_por_causa_metrics,
	update_monitoring_summary_metrics,
	update_nodo_connection_metrics,
	update_sensor_metrics_by_cama,
)
from app.services import query_service

logger = logging.getLogger(__name__)
NOISY_PATHS = {"/health", "/metrics"}
SLOW_REQUEST_WARN_MS = float(os.getenv("SLOW_REQUEST_WARN_MS", "5000"))
_metrics_refresh_stop_event = threading.Event()
_metrics_refresh_thread: threading.Thread | None = None


def _setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _refresh_custom_metrics_once() -> None:
    db = SessionLocal()
    try:
        camas = query_service.list_camas(db)
        summary = query_service.get_monitoring_summary(
            db,
            disconnect_minutes=settings.monitoring_disconnect_minutes,
        )
        sensor_by_cama = query_service.get_latest_sensor_averages_by_cama(db)
        nodos_conexion = query_service.get_all_nodos_connection_status(
            db,
            minutes=settings.monitoring_disconnect_minutes,
        )
        errores_por_nodo = query_service.get_errores_count_by_nodo(db)
        invalidaciones_por_causa = query_service.get_invalidaciones_count_by_causa(db)
        update_cama_info_metrics(camas)
        update_monitoring_summary_metrics(summary)
        update_sensor_metrics_by_cama(sensor_by_cama)
        update_nodo_connection_metrics(nodos_conexion)
        update_errores_por_nodo_metrics(errores_por_nodo)
        update_invalidaciones_por_causa_metrics(invalidaciones_por_causa)
    except Exception:
        logger.exception("Failed to refresh custom monitoring metrics")
    finally:
        db.close()


def _custom_metrics_refresh_loop() -> None:
    refresh_interval = settings.monitoring_metrics_refresh_seconds
    logger.info(
        "Custom metrics refresher started interval_s=%s disconnect_minutes=%s",
        refresh_interval,
        settings.monitoring_disconnect_minutes,
    )
    while not _metrics_refresh_stop_event.wait(refresh_interval):
        _refresh_custom_metrics_once()
    logger.info("Custom metrics refresher stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Read-only service — tables are owned and created by the write services
    global _metrics_refresh_thread

    logger.info("Starting query-monitoring-service")
    _metrics_refresh_stop_event.clear()
    _refresh_custom_metrics_once()
    _metrics_refresh_thread = threading.Thread(target=_custom_metrics_refresh_loop, name="query-metrics-refresh", daemon=True)
    _metrics_refresh_thread.start()

    yield

    _metrics_refresh_stop_event.set()
    if _metrics_refresh_thread and _metrics_refresh_thread.is_alive():
        _metrics_refresh_thread.join(timeout=3)
    _metrics_refresh_thread = None
    logger.info("Stopping query-monitoring-service")


_setup_logging()
app = FastAPI(title="Query Monitoring Service", lifespan=lifespan)


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
