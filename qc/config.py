"""Settings and dated model price table read from the environment and .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Price table in USD per 1M tokens: (input_per_1m, output_per_1m), verified 2026-11-18.
MODEL_PRICES_USD_PER_M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-5-mini": (0.25, 2.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
}

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5",
    "stub": "stub",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://qc:qc@localhost:5433/qc"
    embed_provider: str = "e5"
    embed_model: str = "intfloat/multilingual-e5-small"
    reuse_threshold: float = 0.90
    min_evidence: float = 0.30
    chunk_max_chars: int = 1200

    llm_provider: str = "stub"
    llm_model: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    max_eval_cost_usd: float = 1.00


@lru_cache
def get_settings() -> Settings:
    return Settings()
