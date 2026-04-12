from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import UTC, datetime

from app.broker.contracts import BrokerEnvelope, MessageBroker, MessageHandler, MessagePayload

try:
    import pika
except Exception:
    pika = None


class RabbitMQBroker(MessageBroker):
    def __init__(
        self,
        *,
        amqp_url: str,
        queue_name: str,
        exchange: str,
        routing_key: str,
        prefetch_count: int,
        logger: logging.Logger | None = None,
    ):
        self._logger = logger or logging.getLogger(__name__)
        self._amqp_url = amqp_url
        self._queue_name = queue_name
        self._exchange = exchange
        self._routing_key = routing_key
        self._prefetch_count = max(prefetch_count, 1)
        self._stop_event = threading.Event()
        self._consumer_thread: threading.Thread | None = None

    def _ensure_dependency(self) -> None:
        if pika is None:
            raise RuntimeError("pika is required for RabbitMQ broker support")

    def publish(self, topic: str, payload: MessagePayload, headers: dict[str, str] | None = None) -> str:
        self._ensure_dependency()
        message_id = str(uuid.uuid4())
        routing_key = self._routing_key or topic
        body = json.dumps(payload).encode("utf-8")

        params = pika.URLParameters(self._amqp_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=self._queue_name, durable=True)
        channel.basic_publish(
            exchange=self._exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                message_id=message_id,
                timestamp=int(datetime.now(UTC).timestamp()),
                headers=headers or {},
            ),
        )
        connection.close()
        return message_id

    def start_consumer(self, topic: str, handler: MessageHandler) -> None:
        self._ensure_dependency()
        if self._consumer_thread and self._consumer_thread.is_alive():
            return

        self._stop_event.clear()

        def _consume_loop() -> None:
            params = pika.URLParameters(self._amqp_url)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=self._queue_name, durable=True)
            channel.basic_qos(prefetch_count=self._prefetch_count)

            while not self._stop_event.is_set():
                method_frame, properties, body = channel.basic_get(queue=self._queue_name, auto_ack=False)
                if method_frame is None:
                    self._stop_event.wait(0.2)
                    continue

                try:
                    payload = json.loads(body.decode("utf-8"))
                    envelope = BrokerEnvelope(
                        message_id=(properties.message_id if properties and properties.message_id else str(uuid.uuid4())),
                        topic=topic,
                        payload=payload,
                        timestamp=datetime.now(UTC),
                        headers=(properties.headers if properties and properties.headers else {}),
                    )
                    handler(envelope)
                    channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                except Exception:
                    self._logger.exception("Error processing RabbitMQ message")
                    channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)

            channel.close()
            connection.close()

        self._consumer_thread = threading.Thread(target=_consume_loop, name="rabbitmq-broker-consumer", daemon=True)
        self._consumer_thread.start()

    def stop_consumer(self) -> None:
        self._stop_event.set()
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5)

    def healthcheck(self) -> bool:
        try:
            self._ensure_dependency()
            params = pika.URLParameters(self._amqp_url)
            connection = pika.BlockingConnection(params)
            connection.close()
            return True
        except Exception:
            return False

    def close(self) -> None:
        self.stop_consumer()
