from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Protocol

MessagePayload = dict[str, Any]


@dataclass(slots=True)
class BrokerEnvelope:
    message_id: str
    topic: str
    payload: MessagePayload
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    headers: dict[str, str] = field(default_factory=dict)


MessageHandler = Callable[[BrokerEnvelope], None]


class MessageBroker(Protocol):
    def publish(self, topic: str, payload: MessagePayload, headers: dict[str, str] | None = None) -> str:
        ...

    def start_consumer(self, topic: str, handler: MessageHandler) -> None:
        ...

    def stop_consumer(self) -> None:
        ...

    def healthcheck(self) -> bool:
        ...

    def close(self) -> None:
        ...
