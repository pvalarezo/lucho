"""Local embedding provider using sentence-transformers (free, offline).

Install with: pip install sentence-transformers
Model: paraphrase-multilingual-MiniLM-L12-v2 (384 dims, Spanish native)

This is an optional alternative to OpenAI embeddings.
Falls back gracefully if sentence-transformers is not installed.
"""

import logging

logger = logging.getLogger(__name__)

LOCAL_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
LOCAL_EMBEDDING_DIM = 384  # this model outputs 384-dimensional vectors

_model = None


def _get_model():
    """Lazy-load the sentence-transformers model."""
    global _model
    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading local embedding model: %s", LOCAL_MODEL_NAME)
        _model = SentenceTransformer(LOCAL_MODEL_NAME)
        logger.info("Local embedding model loaded (%d dimensions)", LOCAL_EMBEDDING_DIM)
        return _model
    except ImportError:
        logger.warning(
            "sentence-transformers not installed. "
            "Install with: pip install sentence-transformers. "
            "Falling back to other embedding providers."
        )
        return None
    except Exception as exc:
        logger.error("Failed to load local embedding model: %s", exc)
        return None


async def generate_embedding(text: str) -> list[float] | None:
    """
    Generate embedding using local sentence-transformers model.
    Returns None if the library is not installed or model fails to load.
    """
    model = _get_model()
    if model is None:
        return None

    try:
        # sentence-transformers encode is synchronous, run in thread
        import asyncio
        embedding = await asyncio.to_thread(
            model.encode, text[:8000], normalize_embeddings=True
        )
        vec = embedding.tolist()
        # Pad to 1024 dimensions to match pgvector VECTOR(1024)
        if len(vec) < 1024:
            vec.extend([0.0] * (1024 - len(vec)))
        return vec
    except Exception as exc:
        logger.error("Local embedding generation failed: %s", exc)
        return None


def is_available() -> bool:
    """Check if local embeddings are available."""
    return _get_model() is not None
