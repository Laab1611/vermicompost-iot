from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://vermicompost:vermicompost@postgres:5432/vermicompost"
    ALERT_SERVICE_URL: str = "http://alert-service:8000"
    DIGITAL_TWIN_SERVICE_URL: str = "http://digital-twin-service:8000"

    model_config = {"env_file": ".env"}


settings = Settings()