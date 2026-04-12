from prometheus_client import Counter, Histogram, Gauge

ingestion_broker_enqueue_total = Counter(
    "ingestion_broker_enqueue_total",
    "Total telemetry payloads enqueued to broker",
)

ingestion_broker_processed_total = Counter(
    "ingestion_broker_processed_total",
    "Total broker messages processed by status",
    ["status"],
)

ingestion_broker_process_seconds = Histogram(
    "ingestion_broker_process_seconds",
    "Seconds spent processing broker ingestion messages",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

# Redis Streams observability metrics
ingestion_redis_stream_length = Gauge(
    "ingestion_redis_stream_length",
    "Total messages currently in Redis stream (telemetry.ingestion)",
)

ingestion_redis_pending_messages = Gauge(
    "ingestion_redis_pending_messages",
    "Pending (unacknowledged) messages in consumer group",
)

ingestion_redis_consumer_lag = Gauge(
    "ingestion_redis_consumer_lag",
    "Consumer lag: messages waiting to be processed (stream_length - pending)",
)

ingestion_batch_buffer_size = Gauge(
    "ingestion_batch_buffer_size",
    "Current size of batch buffer (pending database flush)",
)