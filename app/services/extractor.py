"""Structured extractor — extracts fields from user messages using the configured LLM provider.

Returns structured data based on the target_table determined by the router.
"""

import logging

from app.services.llm import get_llm_provider

logger = logging.getLogger(__name__)


async def extract_fields(text: str, target_table: str) -> dict:
    """
    Extract structured fields from user text based on target_table.
    Uses the configured LLM provider's extractor model.
    """
    provider = get_llm_provider()
    if provider is None:
        logger.warning("No LLM provider configured — returning empty extraction")
        return {}

    logger.info(
        "Extracting fields for target_table=%s with %s: %s",
        target_table,
        type(provider).__name__,
        text[:120],
    )

    try:
        result = await provider.extract(text, target_table)
        logger.info("Extraction complete: %s", str(result)[:200])
        return result
    except Exception as exc:
        logger.error("Extraction failed: %s", exc)
        return {}
