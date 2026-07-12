"""Persistence service — writes extracted data to the correct target tables.

This is DETERMINISTIC code (spec principle: IA en bordes, determinismo en centro).
The LLM only decides the target_table and extracts fields; this service handles
the actual database writes, resolving entities, and enforcing business rules.
"""

import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetType
from app.models.event import Event, EventCertainty, EventStatus
from app.models.list import List, ListItem, ItemStatus, ListType
from app.models.topic import Topic, Note
from app.models.project import Project, ProjectTask, TaskStatus
from app.models.contact import Contact
from app.models.shared_expense import SharedExpense, SharedExpenseParticipant, SplitType, ParticipantStatus

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
    # Guard against null values
    if not name or not name.strip():
        name = "sin nombre"
    if not attributes:
        attributes = {}
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
        try:
            target_date = date.fromisoformat(target_date)
        except (ValueError, TypeError):
            target_date = date.today() + timedelta(days=1)  # default: tomorrow
    elif target_date is None:
        target_date = date.today() + timedelta(days=1)

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
    if not list_name or not list_name.strip():
        list_name = "general"
    if not items:
        return []
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

        # Generate embedding
        from app.services import embeddings as embed_svc
        embedding = await embed_svc.generate_embedding(item_text.strip())
        if embedding:
            item.embedding = embedding

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
    # Guard against null/empty topic names from extractor
    if not topic_name or not topic_name.strip():
        topic_name = "general"
    if not content or not content.strip():
        content = "(sin contenido)"
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

    # Generate embedding asynchronously (non-blocking)
    from app.services import embeddings as embed_svc
    embedding = await embed_svc.generate_embedding(content)
    if embedding:
        note.embedding = embedding
        await session.flush()
    logger.info("Created note %s in topic '%s'", note.id, topic_name)
    return note


# ---- Projects ----

async def persist_project_task(
    session: AsyncSession,
    user_id: uuid.UUID,
    project_name: str,
    content: str,
    due_date: date | None = None,
) -> ProjectTask:
    """Create a task in a project. Creates the project if it doesn't exist."""
    if not project_name or not project_name.strip():
        project_name = "general"

    # Resolve or create project
    result = await session.execute(
        select(Project).where(
            Project.user_id == user_id,
            Project.name == project_name,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        project = Project(user_id=user_id, name=project_name)
        session.add(project)
        await session.flush()
        logger.info("Created project: %s", project_name)

    task = ProjectTask(
        project_id=project.id,
        content=content,
        due_date=due_date,
    )
    session.add(task)
    await session.flush()
    logger.info("Added task '%s' to project '%s'", content[:60], project_name)
    return task


# ---- Shared Expenses ----

async def persist_shared_expense(
    session: AsyncSession,
    user_id: uuid.UUID,
    description: str,
    total_amount: float,
    participants: list[str],
    split_type: str = "equal",
    currency: str = "USD",
    expense_date: date | None = None,
) -> SharedExpense:
    """Create a shared expense with participants."""
    if not description:
        description = "gasto compartido"
    if not participants:
        participants = ["otro"]

    try:
        st = SplitType(split_type)
    except ValueError:
        st = SplitType.equal

    if expense_date is None:
        expense_date = date.today()

    per_person = total_amount / len(participants) if participants else total_amount

    expense = SharedExpense(
        user_id=user_id,
        description=description,
        total_amount=total_amount,
        currency=currency,
        split_type=st,
        expense_date=expense_date,
    )
    session.add(expense)
    await session.flush()

    for name in participants:
        participant = SharedExpenseParticipant(
            expense_id=expense.id,
            name=name.strip(),
            amount=per_person,
        )
        session.add(participant)

    await session.flush()
    logger.info(
        "Created shared expense: %s $%.2f / %d people = $%.2f c/u",
        description, total_amount, len(participants), per_person,
    )
    return expense


# ---- Contacts ----

async def persist_contact(
    session: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    phone_number: str | None = None,
    relationship: str | None = None,
) -> Contact:
    """Create a contact for the user."""
    if not name or not name.strip():
        name = "sin nombre"

    contact = Contact(
        user_id=user_id,
        name=name,
        phone_number=phone_number,
        relationship=relationship,
    )
    session.add(contact)
    await session.flush()
    logger.info("Created contact: %s", name)
    return contact
