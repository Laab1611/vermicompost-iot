from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.broker.contracts import BrokerEnvelope, MessageBroker
from app.broker.factory import create_broker
from app.config import Settings, settings
from app.exceptions import PersistenceError
from app.metrics.prometheus import (
    ingestion_broker_enqueue_total,
    ingestion_broker_process_seconds,
    ingestion_broker_processed_total,
    ingestion_redis_stream_length,
    ingestion_redis_pending_messages,
    ingestion_redis_consumer_lag,
    ingestion_batch_buffer_size,
)

logger = logging.getLogger(__name__)

Processor = Callable[[dict[str, Any]], dict[str, Any]]
BatchFlusher = Callable[[list[dict[str, Any]], dict[int, datetime]], int]


class BrokerIngestionRuntime:
    def __init__(self, app_settings: Settings, processor: Processor, batch_flusher: BatchFlusher):
        self._settings = app_settings
        self._processor = processor
        self._batch_flusher = batch_flusher
        self._broker: MessageBroker | None = None
        self._consumer_started = False

        self._batch_lock = threading.Lock()
        self._batch_rows: list[dict[str, Any]] = []
        self._batch_last_seen_by_nodo: dict[int, datetime] = {}
        self._last_flush_monotonic = time.monotonic()

        self._flush_stop_event = threading.Event()
        self._flush_thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return self._settings.ingestion_mode == "broker"

    def initialize(self) -> None:
        if not self.enabled:
            logger.info("Broker runtime disabled, ingestion mode is sync")
            return

        self._broker = create_broker(self._settings, logger=logger)
        logger.info("Broker runtime enabled with provider=%s", self._settings.broker_provider)

        if self._settings.broker_consumer_enabled:
            self._broker.start_consumer(self._settings.broker_queue_name, self._handle_message)
            self._consumer_started = True
            logger.info("Broker consumer started on queue=%s", self._settings.broker_queue_name)

        self._flush_stop_event.clear()
        self._flush_thread = threading.Thread(target=self._flush_loop, name="broker-ingestion-batch-flusher", daemon=True)
        self._flush_thread.start()

    def enqueue(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise PersistenceError("broker runtime is disabled")
        if self._broker is None:
            raise PersistenceError("broker runtime is not initialized")

        try:
            message_id = self._broker.publish(
                topic=self._settings.broker_queue_name,
                payload=payload,
                headers={"service": "telemetry-ingestion-service"},
            )
            ingestion_broker_enqueue_total.inc()
            return {
                "message": f"Lectura encolada ({message_id})",
                "lectura_id": None,
                "es_valida": True,
                "motivo_invalidacion": None,
                "persistida": False,
            }
        except Exception as exc:
            logger.exception("Error publishing telemetry payload to broker")
            raise PersistenceError("error al encolar ingesta") from exc

    def shutdown(self) -> None:
        self._flush_stop_event.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=3)
        self._flush_pending(force=True)

        if self._broker is None:
            logger.info("Broker runtime shutdown complete")
            return

        if self._consumer_started:
            self._broker.stop_consumer()
            self._consumer_started = False

        self._broker.close()
        self._broker = None
        logger.info("Broker runtime shutdown complete")

    def _handle_message(self, envelope: BrokerEnvelope) -> None:
        start = time.perf_counter()
        status = "ok"
        try:
            result = self._processor(envelope.payload)
            if result.get("status") == "valid":
                self._append_batch(
                    result["lectura_data"],
                    result["nodo_id"],
                    result["fecha_recepcion"],
                )
        except Exception:
            status = "error"
            raise
        finally:
            elapsed = max(time.perf_counter() - start, 0.0)
            ingestion_broker_processed_total.labels(status=status).inc()
            ingestion_broker_process_seconds.observe(elapsed)

    def _append_batch(self, lectura_data: dict[str, Any], nodo_id: int, fecha_recepcion: datetime) -> None:
        should_flush = False
        with self._batch_lock:
            self._batch_rows.append(lectura_data)
            existing = self._batch_last_seen_by_nodo.get(nodo_id)
            if existing is None or fecha_recepcion > existing:
                self._batch_last_seen_by_nodo[nodo_id] = fecha_recepcion

            if len(self._batch_rows) >= self._settings.broker_batch_size:
                should_flush = True

        if should_flush:
            self._flush_pending(force=True)

    def _flush_loop(self) -> None:
        while not self._flush_stop_event.wait(0.2):
            self._flush_pending(force=False)
            self._update_metrics()

    def _update_metrics(self) -> None:
        """Actualizar métricas de Prometheus para observabilidad."""
        try:
            with self._batch_lock:
                buffer_size = len(self._batch_rows)
                ingestion_batch_buffer_size.set(buffer_size)

            # Si tenemos broker, obtener info de stream
            if self._broker is not None and hasattr(self._broker, "get_stream_status"):
                status = self._broker.get_stream_status()
                stream_len = status.get("stream_length", 0)
                pending = status.get("pending_messages", 0)
                ingestion_redis_stream_length.set(stream_len)
                ingestion_redis_pending_messages.set(pending)
                # consumer_lag = messages en stream que no están pendientes
                lag = max(stream_len - pending, 0)
                ingestion_redis_consumer_lag.set(lag)
        except Exception:
            logger.exception("Error updating metrics")

    def _flush_pending(self, force: bool) -> None:
        rows: list[dict[str, Any]]
        last_seen: dict[int, datetime]

        with self._batch_lock:
            if not self._batch_rows:
                return

            elapsed = time.monotonic() - self._last_flush_monotonic
            if not force and elapsed < self._settings.broker_flush_seconds:
                return

            rows = list(self._batch_rows)
            last_seen = dict(self._batch_last_seen_by_nodo)
            self._batch_rows.clear()
            self._batch_last_seen_by_nodo.clear()

        try:
            inserted = self._batch_flusher(rows, last_seen)
            self._last_flush_monotonic = time.monotonic()
            logger.debug("Flushed ingestion batch rows=%s inserted=%s", len(rows), inserted)
        except Exception:
            logger.exception("Error flushing broker ingestion batch")
            with self._batch_lock:
                self._batch_rows = rows + self._batch_rows
                for nodo_id, fecha_recepcion in last_seen.items():
                    existing = self._batch_last_seen_by_nodo.get(nodo_id)
                    if existing is None or fecha_recepcion > existing:
                        self._batch_last_seen_by_nodo[nodo_id] = fecha_recepcion


_runtime: BrokerIngestionRuntime | None = None


def initialize_runtime(processor: Processor, batch_flusher: BatchFlusher) -> None:
    global _runtime
    if _runtime is not None:
        return

    _runtime = BrokerIngestionRuntime(settings, processor, batch_flusher)
    _runtime.initialize()


def get_runtime() -> BrokerIngestionRuntime | None:
    return _runtime


def shutdown_runtime() -> None:
    global _runtime
    if _runtime is None:
        return

    _runtime.shutdown()
    _runtime = None
