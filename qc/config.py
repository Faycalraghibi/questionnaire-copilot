"""Settings read from the environment and from .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://qc:qc@localhost:5433/qc"


@lru_cache
def get_settings() -> Settings:
    return Settings()
