from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://vermicompost:vermicompost@postgres:5432/vermicompost"

    model_config = {"env_file": ".env"}


settings = Settings()
