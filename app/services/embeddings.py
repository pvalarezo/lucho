"""Embedding generation service — produces vector embeddings for semantic search.

Uses the configured embedding provider to generate vectors for notes,
list items, and assets. Embeddings are stored in pgvector columns.

Supported providers:
- openai: text-embedding-3-small ($0.02/1M tokens)
- none: skip embedding generation (fallback to ILIKE text search)
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OPENAI_EMBEDDING_URL = "https://api.openai.com/v1/embeddings"
EMBEDDING_DIM = 1024  # must match pgvector VECTOR(1024)


async def generate_embedding(text: str) -> list[float] | None:
    """
    Generate a vector embedding for the given text.
    Returns a list of floats (1024 dimensions) or None on failure.
    """
    if not text or not text.strip():
        return None

    provider = settings.EMBEDDING_PROVIDER

    if provider == "openai":
        return await _openai_embed(text)
    elif provider == "local":
        from app.services import local_embeddings
        return await local_embeddings.generate_embedding(text)
    elif provider == "none":
        return None
    else:
        logger.warning("Unknown EMBEDDING_PROVIDER: %s", provider)
        return None


async def _openai_embed(text: str) -> list[float] | None:
    """Generate embedding using OpenAI's API."""
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — cannot generate embeddings")
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                OPENAI_EMBEDDING_URL,
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.OPENAI_EMBEDDING_MODEL,
                    "input": text[:8000],  # truncate to model limit
                },
            )
            response.raise_for_status()
            data = response.json()
            embedding = data["data"][0]["embedding"]

            # Pad or truncate to EMBEDDING_DIM
            if len(embedding) < EMBEDDING_DIM:
                embedding.extend([0.0] * (EMBEDDING_DIM - len(embedding)))
            elif len(embedding) > EMBEDDING_DIM:
                embedding = embedding[:EMBEDDING_DIM]

            logger.debug("Generated embedding: %d dimensions", len(embedding))
            return embedding

        except (httpx.HTTPError, KeyError, IndexError) as exc:
            logger.error("Embedding generation failed: %s", exc)
            return None


async def generate_search_embedding(query: str) -> list[float] | None:
    """
    Generate an embedding for a search query.
    Same as generate_embedding but with a different log context.
    """
    logger.info("Generating search embedding for: %s", query[:100])
    return await generate_embedding(query)


async def embed_and_store_content(
    content: str,
    target_object,  # Note or ListItem with 'embedding' attribute
) -> None:
    """
    Generate embedding for content and assign it to the target object.
    The caller must flush/commit the session.
    """
    embedding = await generate_embedding(content)
    if embedding is not None:
        target_object.embedding = embedding
        logger.debug("Stored embedding for: %s", content[:60])
