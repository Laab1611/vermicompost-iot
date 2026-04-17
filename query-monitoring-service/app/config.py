from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    MONITORING_METRICS_REFRESH_SECONDS: int = Field(default=30, ge=5, le=3600)
    MONITORING_DISCONNECT_MINUTES: int = Field(default=15, ge=1, le=43200)

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def monitoring_metrics_refresh_seconds(self) -> int:
        return self.MONITORING_METRICS_REFRESH_SECONDS

    @property
    def monitoring_disconnect_minutes(self) -> int:
        return self.MONITORING_DISCONNECT_MINUTES


settings = Settings()