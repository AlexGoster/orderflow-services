from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "OrderFlow Gateway"

    catalog_service_url: str = "http://localhost:8001"
    order_service_url: str = "http://localhost:8002"
    notification_service_url: str = "http://localhost:8003"
    timeout: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
