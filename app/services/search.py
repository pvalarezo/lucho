"""Semantic search service — find user content using pgvector embeddings.

Two search modes:
1. Semantic search: pgvector cosine similarity across notes, list_items, documents
2. Deterministic queries: catalogue of pre-written parametrized SQL queries

Design principle (spec §9.1): never Text2SQL for the user — the LLM extracts
search parameters into a Pydantic model, and this service runs a pre-written query.
"""

import logging
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import text, select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.event import Event, EventStatus
from app.models.topic import Note
from app.models.list import ListItem, ItemStatus

logger = logging.getLogger(__name__)


# ---- Semantic search (pgvector) ----

async def semantic_search(
    session: AsyncSession,
    user_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = 5,
    source_tables: list[str] | None = None,
) -> list[dict]:
    """
    Search user content by embedding similarity using pgvector cosine distance.
    Searches: notes, list_items, and assets (by name).

    Returns results sorted by relevance (1 - cosine_distance = similarity).
    """
    results = []

    # Search notes
    if source_tables is None or "notes" in source_tables:
        note_results = await session.execute(
            select(
                Note.id,
                Note.content.label("text"),
                Note.created_at,
                (1 - Note.embedding.cosine_distance(query_embedding)).label("similarity"),
            )
            .join(Note.topic)
            .where(
                Note.embedding.isnot(None),
                Note.topic.has(user_id=user_id),
            )
            .order_by(Note.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        for row in note_results:
            results.append({
                "id": str(row.id),
                "source": "note",
                "text": row.text,
                "similarity": round(float(row.similarity), 4),
                "created_at": row.created_at.isoformat(),
            })

    # Search list_items
    if source_tables is None or "lists" in source_tables:
        list_results = await session.execute(
            select(
                ListItem.id,
                ListItem.content.label("text"),
                ListItem.created_at,
                (1 - ListItem.embedding.cosine_distance(query_embedding)).label("similarity"),
            )
            .join(ListItem.list)
            .where(
                ListItem.embedding.isnot(None),
                ListItem.list.has(user_id=user_id),
            )
            .order_by(ListItem.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        for row in list_results:
            results.append({
                "id": str(row.id),
                "source": "list_item",
                "text": row.text,
                "similarity": round(float(row.similarity), 4),
                "created_at": row.created_at.isoformat(),
            })

    # Search documents (new table)
    if source_tables is None or "documents" in source_tables:
        doc_results = await session.execute(
            select(
                Document.id,
                Document.name.label("text"),
                Document.document_type,
                Document.created_at,
            )
            .where(
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
            )
            .limit(top_k)
        )
        for row in doc_results:
            results.append({
                "id": str(row.id),
                "source": "document",
                "text": f"{row.document_type}: {row.text}",
                "similarity": 1.0,
                "created_at": row.created_at.isoformat(),
            })

    # Sort by similarity descending
    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results[:top_k]


# ---- Deterministic queries (parametrized catalogue) ----

async def spending_by_category(
    session: AsyncSession,
    user_id: uuid.UUID,
    category: str | None = None,
    days: int = 30,
) -> dict:
    """
    "¿cuánto llevo gastado en X?"
    Queries the transactions table for expense totals by category.
    """
    from app.models.transaction import Transaction, TransactionType, TransactionCategory

    since = date.today() - timedelta(days=days)
    since_dt = datetime.combine(since, datetime.min.time())

    filters = [
        Transaction.user_id == user_id,
        Transaction.type == TransactionType.expense,
        Transaction.transaction_date >= since_dt,
    ]
    if category:
        try:
            cat_enum = TransactionCategory(category)
            filters.append(Transaction.category == cat_enum)
        except ValueError:
            pass

    result = await session.execute(
        select(
            Transaction.category,
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .where(*filters)
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
    )

    items = []
    total = 0.0
    for row in result:
        cat_value = row.category.value if hasattr(row.category, 'value') else str(row.category)
        amount = float(row.total or 0)
        items.append({
            "category": cat_value,
            "total": amount,
            "count": row.count,
        })
        total += amount

    return {
        "category": category or "all",
        "period_days": days,
        "since": since.isoformat(),
        "total": total,
        "by_category": items,
    }


async def upcoming_deadlines(
    session: AsyncSession,
    user_id: uuid.UUID,
    days_ahead: int = 30,
) -> list[dict]:
    """
    "¿qué me falta pagar este mes?"
    Returns events with upcoming target_dates.
    """
    today = datetime.now()
    until = today + timedelta(days=days_ahead)

    result = await session.execute(
        select(Event)
        .where(
            Event.user_id == user_id,
            Event.status == EventStatus.upcoming,
            Event.target_date >= today,
            Event.target_date <= until,
        )
        .order_by(Event.target_date)
    )

    deadlines = []
    for event in result.scalars():
        days_left = (event.target_date.date() - today.date()).days
        deadlines.append({
            "id": str(event.id),
            "title": event.title,
            "target_date": event.target_date.isoformat(),
            "days_left": days_left,
            "certainty": event.certainty.value,
        })

    return deadlines


async def list_pending_items(
    session: AsyncSession,
    user_id: uuid.UUID,
    list_name: str | None = None,
) -> list[dict]:
    """
    "¿qué me falta comprar?"
    Returns pending items, optionally filtered by list name.
    """
    query = (
        select(ListItem)
        .options(joinedload(ListItem.list))
        .join(ListItem.list)
        .where(
            ListItem.list.has(user_id=user_id),
            ListItem.status == ItemStatus.pending,
        )
        .order_by(ListItem.created_at)
    )

    if list_name:
        query = query.where(ListItem.list.has(name=list_name))

    result = await session.execute(query)
    items = []
    for item in result.unique().scalars():
        items.append({
            "id": str(item.id),
            "list": item.list.name if item.list else "?",
            "content": item.content,
            "created_at": item.created_at.isoformat(),
        })

    return items


async def search_by_text(
    session: AsyncSession,
    user_id: uuid.UUID,
    search_text: str,
    limit: int = 10,
) -> list[dict]:
    """
    Simple text search across notes and list items using ILIKE.
    Fallback for when embeddings are not available.
    """
    pattern = f"%{search_text}%"
    results = []

    # Search notes
    note_results = await session.execute(
        select(Note.id, Note.content.label("text"), Note.created_at)
        .join(Note.topic)
        .where(
            Note.topic.has(user_id=user_id),
            Note.content.ilike(pattern),
        )
        .limit(limit)
    )
    for row in note_results:
        results.append({
            "id": str(row.id),
            "source": "note",
            "text": row.text[:200],
            "created_at": row.created_at.isoformat(),
        })

    # Search list_items
    list_results = await session.execute(
        select(ListItem.id, ListItem.content.label("text"), ListItem.created_at)
        .join(ListItem.list)
        .where(
            ListItem.list.has(user_id=user_id),
            ListItem.content.ilike(pattern),
        )
        .limit(limit)
    )
    for row in list_results:
        results.append({
            "id": str(row.id),
            "source": "list_item",
            "text": row.text[:200],
            "created_at": row.created_at.isoformat(),
        })

    return results[:limit]
