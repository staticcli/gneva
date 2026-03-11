"""Gneva configuration — loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://gneva:gneva@localhost:5432/gneva"
    database_url_sync: str = "postgresql://gneva:gneva@localhost:5432/gneva"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    algorithm: str = "HS256"

    # Recall.ai
    recall_api_key: str = ""
    recall_api_url: str = "https://api.recall.ai/api/v1"
    recall_webhook_url: str = ""  # public URL for Recall to call back

    # Anthropic
    anthropic_api_key: str = ""

    # ElevenLabs (Stage 4+)
    elevenlabs_api_key: str = ""

    # Storage
    audio_storage_path: str = "/tmp/gneva/audio"
    s3_bucket: str = ""
    s3_region: str = "auto"
    s3_endpoint: str = ""  # for R2

    # Pipeline
    whisper_model: str = "large-v3"
    whisper_device: str = "cuda"  # cuda or cpu
    embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_dim: int = 384

    # App
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8100"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
