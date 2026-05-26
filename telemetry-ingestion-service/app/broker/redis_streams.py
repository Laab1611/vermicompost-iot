from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import UTC, datetime

from redis import Redis
from redis.exceptions import ResponseError

from app.broker.contracts import BrokerEnvelope, MessageBroker, MessageHandler, MessagePayload


class RedisStreamsBroker(MessageBroker):
    def __init__(
        self,
        *,
        redis_url: str,
        stream_key: str,
        consumer_group: str,
        consumer_name: str,
        prefetch_count: int,
        poll_timeout_ms: int,
        logger: logging.Logger | None = None,
    ):
        self._logger = logger or logging.getLogger(__name__)
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._stream_key = stream_key
        self._consumer_group = consumer_group
        self._consumer_name = consumer_name
        self._prefetch_count = max(prefetch_count, 1)
        self._poll_timeout_ms = max(poll_timeout_ms, 100)

        self._stop_event = threading.Event()
        self._consumer_thread: threading.Thread | None = None

    def publish(self, topic: str, payload: MessagePayload, headers: dict[str, str] | None = None) -> str:
        message_id = str(uuid.uuid4())
        self._redis.xadd(
            self._stream_key,
            {
                "message_id": message_id,
                "topic": topic,
                "payload": json.dumps(payload),
                "headers": json.dumps(headers or {}),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        return message_id

    def start_consumer(self, topic: str, handler: MessageHandler) -> None:
        if self._consumer_thread and self._consumer_thread.is_alive():
            return

        self._stop_event.clear()
        self._ensure_group()

        def _consume_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    records = self._read_batch()
                    if not records:
                        continue

                    for record_id, fields in records:
                        try:
                            payload = json.loads(fields.get("payload", "{}"))
                            headers = json.loads(fields.get("headers", "{}"))
                            envelope = BrokerEnvelope(
                                message_id=fields.get("message_id", str(uuid.uuid4())),
                                topic=fields.get("topic", topic),
                                payload=payload,
                                timestamp=datetime.now(UTC),
                                headers=headers,
                            )
                            handler(envelope)
                            self._redis.xack(self._stream_key, self._consumer_group, record_id)
                        except Exception:
                            self._logger.exception("Error processing Redis Streams message %s", record_id)
                except Exception:
                    self._logger.exception("Redis Streams consumer loop error")

        self._consumer_thread = threading.Thread(target=_consume_loop, name="redis-streams-broker-consumer", daemon=True)
        self._consumer_thread.start()

    def stop_consumer(self) -> None:
        self._stop_event.set()
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5)

    def healthcheck(self) -> bool:
        try:
            self._redis.ping()
            return True
        except Exception:
            return False

    def get_stream_status(self) -> dict[str, int]:
        """
        Retorna info del stream para observabilidad:
          - stream_length: total de mensajes retenidos en el stream.
          - pending_messages: mensajes pendientes de acknowledge en el consumer group.
          - consumer_lag: lag real del consumer group según XINFO GROUPS,
            o 0 si no está disponible o el grupo no existe.
        """
        try:
            stream_len = self._redis.xlen(self._stream_key)
            groups = self._redis.xinfo_groups(self._stream_key)

            # Buscar nuestro consumer group por nombre.
            group = None
            for g in groups:
                if g.get("name") == self._consumer_group:
                    group = g
                    break

            if group is not None:
                pending_count = int(group.get("pending", 0))
                raw_lag = group.get("lag")
                # Redis reports lag as None when tracking is temporarily unavailable.
                consumer_lag = int(raw_lag) if raw_lag is not None else 0
            else:
                pending_count = 0
                consumer_lag = 0

            return {
                "stream_length": stream_len,
                "pending_messages": pending_count,
                "consumer_lag": consumer_lag,
            }
        except ResponseError as exc:
            # API-only instances may query before/without a consumer group.
            if "NOGROUP" in str(exc) or "no such key" in str(exc).lower():
                return {
                    "stream_length": self._redis.xlen(self._stream_key),
                    "pending_messages": 0,
                    "consumer_lag": 0,
                }
            self._logger.warning("Error fetching Redis stream status: %s", exc)
            return {
                "stream_length": 0,
                "pending_messages": 0,
                "consumer_lag": 0,
            }
        except Exception as e:
            self._logger.warning("Error fetching Redis stream status: %s", e)
            return {
                "stream_length": 0,
                "pending_messages": 0,
                "consumer_lag": 0,
            }

    def close(self) -> None:
        self.stop_consumer()
        self._redis.close()

    def _ensure_group(self) -> None:
        try:
            self._redis.xgroup_create(self._stream_key, self._consumer_group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def _read_batch(self) -> list[tuple[str, dict[str, str]]]:
        # Process pending messages for this consumer first, then read new records.
        pending = self._redis.xreadgroup(
            groupname=self._consumer_group,
            consumername=self._consumer_name,
            streams={self._stream_key: "0"},
            count=1,
        )
        if pending and pending[0][1]:
            return pending[0][1]

        fresh = self._redis.xreadgroup(
            groupname=self._consumer_group,
            consumername=self._consumer_name,
            streams={self._stream_key: ">"},
            count=self._prefetch_count,
            block=self._poll_timeout_ms,
        )
        if not fresh:
            return []
        return fresh[0][1]
