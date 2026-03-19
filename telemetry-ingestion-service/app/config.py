from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str | None = None
    POSTGRES_USER: str = "vermicompost"
    POSTGRES_PASSWORD: str = "vermicompost"
    POSTGRES_DB: str = "vermicompost"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    DB_SSLMODE: str | None = None
    ALERT_SERVICE_URL: str = "http://alert-service:8000"
    DIGITAL_TWIN_SERVICE_URL: str = "http://digital-twin-service:8000"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL

        base_url = (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
        if self.DB_SSLMODE:
            return f"{base_url}?sslmode={self.DB_SSLMODE}"
        return base_url


settings = Settings()