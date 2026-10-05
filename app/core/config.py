from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "payments-service"
    api_key: str = "change-me"

    database_url: str = "postgresql+asyncpg://payments:payments@localhost:5432/payments"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    outbox_poll_interval: float = 1.0
    outbox_batch_size: int = 50

    webhook_timeout: float = 10.0
    webhook_max_attempts: int = 3

    processing_min_seconds: float = 2.0
    processing_max_seconds: float = 5.0
    processing_success_rate: float = 0.9


@lru_cache
def get_settings() -> Settings:
    return Settings()
