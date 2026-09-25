from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "OrderFlow Order Service"
    database_url: str = "sqlite+aiosqlite:///./order.db"

    bus_backend: str = "redis"
    redis_url: str = "redis://localhost:6379/0"

    catalog_service_url: str = "http://localhost:8001"
    catalog_timeout: float = 3.0
    catalog_max_attempts: int = 3
    catalog_failure_threshold: int = 3
    catalog_recovery_timeout: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
