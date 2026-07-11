"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized settings for Lucho, loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Application ----
    APP_NAME: str = "Lucho"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ---- Database ----
    DATABASE_URL: str = (
        "postgresql+asyncpg://lucho:lucho@localhost:5432/lucho"
    )

    # ---- Redis ----
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---- MinIO ----
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "lucho"
    MINIO_SECURE: bool = False

    # ---- Telegram ----
    TELEGRAM_BOT_TOKEN: str = ""

    # ---- LLM / Anthropic ----
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_HAIKU_MODEL: str = "claude-3-5-haiku-latest"
    ANTHROPIC_SONNET_MODEL: str = "claude-3-5-sonnet-latest"

    # ---- OpenAI (Whisper) ----
    OPENAI_API_KEY: str = ""


settings = Settings()
