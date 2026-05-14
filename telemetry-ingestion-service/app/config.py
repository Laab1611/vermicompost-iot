import os
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    INGESTION_MODE: str = "sync"
    BROKER_PROVIDER: str = "redis"
    BROKER_QUEUE_NAME: str = "telemetry.ingestion"
    BROKER_CONSUMER_ENABLED: bool = True
    BROKER_PREFETCH_COUNT: int = 100
    BROKER_BATCH_SIZE: int = 100
    BROKER_FLUSH_SECONDS: float = 1.0

    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_CONSUMER_GROUP: str = "telemetry-ingestion-group"
    REDIS_CONSUMER_NAME: str = "telemetry-ingestion-consumer"
    REDIS_POLL_TIMEOUT_MS: int = 1000

    MYSQL_URL: str = ""
    MYSQL_HOST: str = "mysql"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = ""
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = ""
    MYSQL_TABLE: str = "sensoresiot"
    MYSQL_BATCH_SIZE: int = 100
    MYSQL_POLL_INTERVAL_SECONDS: float = 30.0
    MYSQL_CHECKPOINT_PATH: str = "/var/lib/mysql-sync/checkpoint.json"
    MYSQL_NODE_ID_MAP: str = ""
    MYSQL_TEMPERATURE_TYPE_ID: int = 0
    MYSQL_HUMIDITY_TYPE_ID: int = 0
    MYSQL_PH_TYPE_ID: int = 0

    # RabbitMQ config temporarily disabled.
    # RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/%2F"
    # RABBITMQ_EXCHANGE: str = ""
    # RABBITMQ_ROUTING_KEY: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def ingestion_mode(self) -> str:
        return self.INGESTION_MODE.strip().lower()

    @property
    def broker_provider(self) -> str:
        return self.BROKER_PROVIDER.strip().lower()

    @property
    def broker_queue_name(self) -> str:
        return self.BROKER_QUEUE_NAME.strip()

    @property
    def broker_consumer_enabled(self) -> bool:
        return bool(self.BROKER_CONSUMER_ENABLED)

    @property
    def broker_prefetch_count(self) -> int:
        return max(int(self.BROKER_PREFETCH_COUNT), 1)

    @property
    def broker_batch_size(self) -> int:
        return max(int(self.BROKER_BATCH_SIZE), 1)

    @property
    def broker_flush_seconds(self) -> float:
        return max(float(self.BROKER_FLUSH_SECONDS), 0.1)

    @property
    def redis_url(self) -> str:
        return self.REDIS_URL.strip()

    @property
    def redis_consumer_group(self) -> str:
        return self.REDIS_CONSUMER_GROUP.strip()

    @property
    def redis_consumer_name(self) -> str:
        raw_name = self.REDIS_CONSUMER_NAME.strip()
        if not raw_name:
            raw_name = "telemetry-ingestion-consumer-{hostname}-{pid}"

        return (
            raw_name.replace("{hostname}", os.getenv("HOSTNAME", "unknown"))
            .replace("{pid}", str(os.getpid()))
        )

    @property
    def redis_poll_timeout_ms(self) -> int:
        return max(int(self.REDIS_POLL_TIMEOUT_MS), 100)

    @property
    def mysql_batch_size(self) -> int:
        return max(int(self.MYSQL_BATCH_SIZE), 1)

    @property
    def mysql_poll_interval_seconds(self) -> float:
        return max(float(self.MYSQL_POLL_INTERVAL_SECONDS), 0.5)

    @property
    def mysql_checkpoint_path(self) -> str:
        return self.MYSQL_CHECKPOINT_PATH.strip() or "/var/lib/mysql-sync/checkpoint.json"

    @property
    def mysql_table(self) -> str:
        return self.MYSQL_TABLE.strip() or "sensoresiot"

    @property
    def mysql_node_id_map(self) -> dict[int, int]:
        raw_map = self.MYSQL_NODE_ID_MAP.strip()
        if not raw_map:
            return {}

        mapping: dict[int, int] = {}
        for item in raw_map.split(","):
            part = item.strip()
            if not part:
                continue
            legacy, sep, target = part.partition(":")
            if not sep:
                continue
            try:
                mapping[int(legacy.strip())] = int(target.strip())
            except ValueError:
                continue
        return mapping

    @property
    def mysql_temperature_type_id(self) -> int:
        return max(int(self.MYSQL_TEMPERATURE_TYPE_ID), 0)

    @property
    def mysql_humidity_type_id(self) -> int:
        return max(int(self.MYSQL_HUMIDITY_TYPE_ID), 0)

    @property
    def mysql_ph_type_id(self) -> int:
        return max(int(self.MYSQL_PH_TYPE_ID), 0)

    @property
    def mysql_connection_url(self) -> str:
        raw_url = self.MYSQL_URL.strip()
        if raw_url:
            return raw_url

        if not self.MYSQL_USER or not self.MYSQL_DATABASE:
            return ""

        credentials = self.MYSQL_USER
        if self.MYSQL_PASSWORD:
            credentials = f"{credentials}:{quote_plus(self.MYSQL_PASSWORD)}"

        host = self.MYSQL_HOST.strip() or "mysql"
        port = max(int(self.MYSQL_PORT), 1)
        return f"mysql+pymysql://{credentials}@{host}:{port}/{self.MYSQL_DATABASE}"

    # RabbitMQ accessors temporarily disabled.
    # @property
    # def rabbitmq_url(self) -> str:
    #     return self.RABBITMQ_URL.strip()

    # @property
    # def rabbitmq_exchange(self) -> str:
    #     return self.RABBITMQ_EXCHANGE.strip()

    # @property
    # def rabbitmq_routing_key(self) -> str:
    #     return self.RABBITMQ_ROUTING_KEY.strip()


settings = Settings()