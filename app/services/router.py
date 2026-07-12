"""Intent router — classifies user messages using the configured LLM provider."""

import logging

from app.services.llm import get_llm_provider

logger = logging.getLogger(__name__)


async def route_intent(text: str) -> dict:
    """
    Classify user message into a target table.
    Returns {"target_table": str, "reasoning": str}.
    Falls back to "note" if no LLM is available.
    """
    provider = get_llm_provider()
    if provider is None:
        logger.warning("No LLM provider configured — defaulting to 'note'")
        return {"target_table": "note", "reasoning": "no_provider_configured"}

    logger.info("Routing intent with %s: %s", type(provider).__name__, text[:120])

    try:
        result = await provider.route(text)
        logger.info(
            "Intent routed → %s (reasoning: %s)",
            result.get("target_table", "?"),
            result.get("reasoning", ""),
        )
        return result
    except Exception as exc:
        logger.error("Intent routing failed: %s", exc)
        return {"target_table": "note", "reasoning": f"router_error: {exc}"}
