from __future__ import annotations

import logging
import queue
import threading
import uuid

from app.broker.contracts import BrokerEnvelope, MessageBroker, MessageHandler, MessagePayload


class InMemoryBroker(MessageBroker):
    def __init__(self, logger: logging.Logger | None = None):
        self._logger = logger or logging.getLogger(__name__)
        self._queue: queue.Queue[BrokerEnvelope] = queue.Queue()
        self._stop_event = threading.Event()
        self._consumer_thread: threading.Thread | None = None

    def publish(self, topic: str, payload: MessagePayload, headers: dict[str, str] | None = None) -> str:
        message_id = str(uuid.uuid4())
        self._queue.put(BrokerEnvelope(message_id=message_id, topic=topic, payload=payload, headers=headers or {}))
        return message_id

    def start_consumer(self, topic: str, handler: MessageHandler) -> None:
        if self._consumer_thread and self._consumer_thread.is_alive():
            return

        self._stop_event.clear()

        def _consume_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    envelope = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                try:
                    if envelope.topic == topic:
                        handler(envelope)
                except Exception:
                    self._logger.exception("Error processing in-memory broker message %s", envelope.message_id)
                finally:
                    self._queue.task_done()

        self._consumer_thread = threading.Thread(target=_consume_loop, name="in-memory-broker-consumer", daemon=True)
        self._consumer_thread.start()

    def stop_consumer(self) -> None:
        self._stop_event.set()
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=3)

    def healthcheck(self) -> bool:
        return True

    def close(self) -> None:
        self.stop_consumer()
