from __future__ import annotations

import logging

from app.broker.contracts import MessageBroker
from app.broker.in_memory import InMemoryBroker
from app.config import Settings

# RabbitMQ provider import temporarily disabled.
# from app.broker.rabbitmq import RabbitMQBroker


def create_broker(settings: Settings, logger: logging.Logger | None = None) -> MessageBroker:
    provider = settings.broker_provider
    if provider == "memory":
        return InMemoryBroker(logger=logger)

    # RabbitMQ provider temporarily disabled.
    # if provider == "rabbitmq":
    #     return RabbitMQBroker(
    #         amqp_url=settings.rabbitmq_url,
    #         queue_name=settings.broker_queue_name,
    #         exchange=settings.rabbitmq_exchange,
    #         routing_key=settings.rabbitmq_routing_key,
    #         prefetch_count=settings.broker_prefetch_count,
    #         logger=logger,
    #     )

    if provider == "redis":
        from app.broker.redis_streams import RedisStreamsBroker

        return RedisStreamsBroker(
            redis_url=settings.redis_url,
            stream_key=settings.broker_queue_name,
            consumer_group=settings.redis_consumer_group,
            consumer_name=settings.redis_consumer_name,
            prefetch_count=settings.broker_prefetch_count,
            poll_timeout_ms=settings.redis_poll_timeout_ms,
            logger=logger,
        )

    raise ValueError(f"Unsupported broker provider: {provider}")
