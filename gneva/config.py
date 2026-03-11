"""Gneva configuration — loaded from environment variables."""

import logging
import sys

from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache

_cfg_logger = logging.getLogger(__name__)

_INSECURE_DEFAULT_KEY = "change-me-in-production"


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://gneva:gneva@localhost:5432/gneva"
    database_url_sync: str = "postgresql://gneva:gneva@localhost:5432/gneva"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = _INSECURE_DEFAULT_KEY
    access_token_expire_minutes: int = 480  # 8 hours
    algorithm: str = "HS256"

    # Meeting Bot
    bot_name: str = "Gneva"
    bot_consent_message: str = "Gneva AI is recording this meeting for notes and action items."
    bot_max_concurrent: int = 5
    bot_lobby_timeout_sec: int = 300
    bot_max_duration_sec: int = 14400  # 4 hours
    bot_consent_required: bool = False

    # Anthropic
    anthropic_api_key: str = ""

    # Local LLM (Ollama)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # Slack (Stage 3)
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_client_id: str = ""
    slack_client_secret: str = ""

    # ElevenLabs (Stage 4+)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # TTS (Stage 4)
    tts_backend: str = "piper"  # piper or elevenlabs
    piper_model_path: str = ""

    # SadTalker (talking head avatar)
    sadtalker_checkpoint_dir: str = ""
    sadtalker_enabled: bool = True  # auto-disabled if checkpoints not found

    # Scheduler (Stage 5)
    scheduler_enabled: bool = True
    weekly_digest_day: int = 4  # Friday (0=Monday)
    weekly_digest_hour: int = 17  # 5 PM

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

    # Email/SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "gneva@yourdomain.com"

    # Calendar
    google_calendar_enabled: bool = False
    outlook_calendar_enabled: bool = False

    # Webhook
    webhook_secret: str = ""

    # App
    debug: bool = False
    sql_echo: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8100"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        if self.secret_key == _INSECURE_DEFAULT_KEY:
            _cfg_logger.critical(
                "SECRET_KEY is set to the insecure default! "
                "Set a strong, unique SECRET_KEY environment variable."
            )
            if not self.debug:
                _cfg_logger.critical("Refusing to start in non-debug mode with default SECRET_KEY.")
                sys.exit(1)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
