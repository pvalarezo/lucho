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
    EMBEDDING_PROVIDER: str = "none"  # "openai" | "local" | "none"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ---- WhatsApp Cloud API ----
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_API_VERSION: str = "v22.0"

    # ---- External APIs ----
    VEHICLE_INFO_API_URL: str = "http://131.161.221.131:2356/v1/info/all/vehicle/"
    VEHICLE_INFO_API_TOKEN: str = ""

    # ---- PayPhone (Ecuador) ----
    PAYPHONE_CLIENT_ID: str = ""
    PAYPHONE_CLIENT_SECRET: str = ""
    PAYPHONE_STORE_ID: str = ""
    PAYPHONE_API_URL: str = "https://api.payphone.app"
    PAYPHONE_WEBHOOK_SECRET: str = ""  # For validating webhook signatures

    # ---- DeUna (Banco Pichincha — Ecuador) ----
    DEUNA_API_KEY: str = ""
    DEUNA_MERCHANT_ID: str = ""

    # ---- Key49 (Facturación electrónica SRI — AURACORE) ----
    KEY49_API_KEY: str = ""
    KEY49_ESTABLISHMENT: str = "001"
    KEY49_ISSUE_POINT: str = "001"

    # ---- Feature Flags ----
    CONTEXTUAL_RESPONSES: bool = True  # LLM-powered conversational answers


settings = Settings()
