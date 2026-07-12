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

    # ---- LLM Provider (anthropic | deepseek) ----
    LLM_PROVIDER: str = "anthropic"

    # ---- Anthropic (Claude) ----
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_HAIKU_MODEL: str = "claude-3-5-haiku-latest"
    ANTHROPIC_SONNET_MODEL: str = "claude-3-5-sonnet-latest"

    # ---- DeepSeek ----
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_ROUTER_MODEL: str = "deepseek-chat"
    DEEPSEEK_EXTRACTOR_MODEL: str = "deepseek-chat"

    # ---- OpenAI (Whisper + Embeddings) ----
    OPENAI_API_KEY: str = ""
    EMBEDDING_PROVIDER: str = "none"  # "openai" | "none"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ---- Feature Flags ----
    CONTEXTUAL_RESPONSES: bool = True  # LLM-powered conversational answers


settings = Settings()
