from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "demo"
    database_url: str = "postgresql+asyncpg://rag:rag@localhost:5432/rag"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-only-change-me-please-32-chars-min"
    access_token_minutes: int = 20
    refresh_token_days: int = 14
    allowed_origins: str = "http://localhost:5173"
    max_upload_mb: int = 25
    chunk_size_tokens: int = 600
    chunk_overlap_tokens: int = 80
    retrieval_top_k: int = 8
    chat_rate_limit_per_minute: int = 30
    embedding_provider: str = "fake"
    embedding_model: str = "fake-hash-v1"
    llm_provider: str = "fake"
    reranker_provider: str = "lexical"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    otel_exporter_otlp_endpoint: str = ""

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return value

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
