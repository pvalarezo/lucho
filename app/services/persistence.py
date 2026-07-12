"""Persistence service — writes extracted data to the correct target tables.

This is DETERMINISTIC code (spec principle: IA en bordes, determinismo en centro).
The LLM only decides the target_table and extracts fields; this service handles
the actual database writes, resolving entities, and enforcing business rules.
"""

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetType
from app.models.event import Event, EventCertainty, EventStatus
from app.models.list import List, ListItem, ItemStatus, ListType
from app.models.topic import Topic, Note

logger = logging.getLogger(__name__)


async def persist_asset(
    session: AsyncSession,
    user_id: uuid.UUID,
    asset_type: str,
    name: str,
    attributes: dict,
    notes: str | None = None,
    source_message_id: uuid.UUID | None = None,
) -> Asset:
    """
    Create or update an asset for the user.
    Resolves duplicates by asset_type + name similarity before inserting.
    """
    # Resolve asset_type enum (with fallback)
    try:
        at_enum = AssetType(asset_type)
    except ValueError:
        logger.warning("Unknown asset_type '%s' — defaulting to 'other'", asset_type)
        at_enum = AssetType.other

    # Check for existing asset (simple exact match on name + type for now)
    result = await session.execute(
        select(Asset).where(
            Asset.user_id == user_id,
            Asset.asset_type == at_enum,
            Asset.name == name,
            Asset.deleted_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        logger.info("Updating existing asset %s (%s)", existing.id, name)
        existing.attributes = {**existing.attributes, **attributes}
        existing.notes = notes or existing.notes
        await session.flush()
        return existing

    # Create new asset
    asset = Asset(
        user_id=user_id,
        asset_type=at_enum,
        name=name,
        attributes=attributes,
        notes=notes,
    )
    session.add(asset)
    await session.flush()
    logger.info("Created asset %s: %s (%s)", asset.id, name, asset_type)
    return asset


async def persist_event(
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    target_date: date | str,
    description: str | None = None,
    certainty: str = "certain",
    recurrence_rule: dict | None = None,
    asset_id: uuid.UUID | None = None,
) -> Event:
    """Create an event for the user."""
    # Parse date if string
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)

    # Resolve certainty enum
    try:
        cert_enum = EventCertainty(certainty)
    except ValueError:
        cert_enum = EventCertainty.estimated

    event = Event(
        user_id=user_id,
        asset_id=asset_id,
        title=title,
        description=description,
        target_date=target_date,
        certainty=cert_enum,
        recurrence_rule=recurrence_rule,
        status=EventStatus.upcoming,
    )
    session.add(event)
    await session.flush()
    logger.info("Created event %s: %s on %s", event.id, title, target_date)
    return event


async def persist_list_items(
    session: AsyncSession,
    user_id: uuid.UUID,
    list_name: str,
    items: list[str],
    quantity: str | None = None,
) -> list[ListItem]:
    """Create or add items to a list. Creates the list if it doesn't exist."""
    # Resolve or create list
    result = await session.execute(
        select(List).where(
            List.user_id == user_id,
            List.name == list_name,
        )
    )
    lst = result.scalar_one_or_none()

    if not lst:
        lst = List(
            user_id=user_id,
            name=list_name,
            list_type=ListType.generic,
        )
        session.add(lst)
        await session.flush()
        logger.info("Created list: %s", list_name)

    # Add items
    created = []
    for item_text in items:
        item = ListItem(
            list_id=lst.id,
            content=item_text.strip(),
            status=ItemStatus.pending,
            quantity=quantity,
        )
        session.add(item)
        created.append(item)

    await session.flush()
    logger.info("Added %d items to list '%s'", len(created), list_name)
    return created


async def persist_note(
    session: AsyncSession,
    user_id: uuid.UUID,
    topic_name: str,
    content: str,
    source_message_id: uuid.UUID | None = None,
) -> Note:
    """Create a note under a topic. Creates the topic if it doesn't exist."""
    # Resolve or create topic
    result = await session.execute(
        select(Topic).where(
            Topic.user_id == user_id,
            Topic.name == topic_name,
        )
    )
    topic = result.scalar_one_or_none()

    if not topic:
        topic = Topic(
            user_id=user_id,
            name=topic_name,
        )
        session.add(topic)
        await session.flush()
        logger.info("Created topic: %s", topic_name)

    note = Note(
        topic_id=topic.id,
        content=content,
        source_message_id=source_message_id,
    )
    session.add(note)
    await session.flush()
    logger.info("Created note %s in topic '%s'", note.id, topic_name)
    return note
