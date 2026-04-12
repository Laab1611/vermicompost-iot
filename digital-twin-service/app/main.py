from contextlib import asynccontextmanager
import logging
import os
import time
import uuid

from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import router

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting digital-twin-service")
    yield
    logger.info("Stopping digital-twin-service")


_setup_logging()
app = FastAPI(title="Digital Twin Service", lifespan=lifespan)


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
