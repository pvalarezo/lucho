"""Search API — conversational search with semantic + deterministic queries."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.services import search as search_svc
from app.services import embeddings as embed_svc

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"], prefix="/search")


@router.get("/semantic")
async def semantic_search(
    q: str = Query(..., description="Search query text"),
    source: str | None = Query(None, description="Filter: notes, lists, assets"),
    top_k: int = Query(5, ge=1, le=20),
    user_id: str = Query(..., description="User UUID"),
    session: AsyncSession = Depends(get_db),
):
    """
    Semantic search across user content using pgvector.
    Requires embeddings (EMBEDDING_PROVIDER configured).
    Falls back to ILIKE text search if embeddings unavailable.
    """
    import uuid as _uuid

    user_uuid = _uuid.UUID(user_id)
    sources = source.split(",") if source else None

    # Try semantic search first
    query_embedding = await embed_svc.generate_search_embedding(q)
    if query_embedding:
        results = await search_svc.semantic_search(
            session=session,
            user_id=user_uuid,
            query_embedding=query_embedding,
            top_k=top_k,
            source_tables=sources,
        )
        return {"query": q, "method": "semantic", "results": results}

    # Fallback to text search
    results = await search_svc.search_by_text(
        session=session,
        user_id=user_uuid,
        search_text=q,
        limit=top_k,
    )
    return {"query": q, "method": "text", "results": results}


@router.get("/deadlines")
async def upcoming_deadlines(
    user_id: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_db),
):
    """Get upcoming deadlines for the next N days."""
    import uuid as _uuid

    deadlines = await search_svc.upcoming_deadlines(
        session=session,
        user_id=_uuid.UUID(user_id),
        days_ahead=days,
    )
    return {"user_id": user_id, "days_ahead": days, "deadlines": deadlines}


@router.get("/pending")
async def pending_items(
    user_id: str = Query(...),
    list_name: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """Get pending list items, optionally filtered by list name."""
    import uuid as _uuid

    items = await search_svc.list_pending_items(
        session=session,
        user_id=_uuid.UUID(user_id),
        list_name=list_name,
    )
    return {"user_id": user_id, "pending": items}
