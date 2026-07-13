"""LLM provider factory — returns the configured provider instance."""

import logging

from app.config import settings
from app.services.llm.anthropic import AnthropicProvider
from app.services.llm.base import LLMProvider
from app.services.llm.deepseek import DeepSeekProvider

logger = logging.getLogger(__name__)

_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider | None:
    """
    Return the configured LLM provider singleton.
    Returns None if no API key is configured for the selected provider.
    """
    global _provider

    if _provider is not None:
        return _provider

    provider_name = settings.LLM_PROVIDER

    match provider_name:
        case "anthropic":
            if not settings.ANTHROPIC_API_KEY:
                logger.warning(
                    "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set"
                )
                return None
            _provider = AnthropicProvider(
                api_key=settings.ANTHROPIC_API_KEY,
                router_model=settings.ANTHROPIC_HAIKU_MODEL,
            )

        case "deepseek":
            if not settings.DEEPSEEK_API_KEY:
                logger.warning(
                    "LLM_PROVIDER=deepseek but DEEPSEEK_API_KEY is not set"
                )
                return None
            _provider = DeepSeekProvider(
                api_key=settings.DEEPSEEK_API_KEY,
                router_model=settings.DEEPSEEK_ROUTER_MODEL,
            )

        case _:
            logger.error("Unknown LLM_PROVIDER: %s", provider_name)
            return None

    logger.info("LLM provider initialized: %s", provider_name)
    return _provider
