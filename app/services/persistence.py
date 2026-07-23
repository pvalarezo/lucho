"""Persistence service — writes extracted data to the correct target tables.

This is DETERMINISTIC code (spec principle: IA en bordes, determinismo en centro).
The LLM only decides the target_table and extracts fields; this service handles
the actual database writes, resolving entities, and enforcing business rules.
"""

import logging
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentType
from app.models.event import Event, EventCertainty, EventStatus
from app.models.list import List, ListItem, ItemStatus, ListType
from app.models.topic import Topic, Note
from app.models.project import Project, ProjectTask
from app.models.contact import Contact
from app.models.transaction import Transaction, Budget, TransactionType, TransactionCategory, BudgetPeriod

logger = logging.getLogger(__name__)


async def persist_document(
    session: AsyncSession,
    user_id: uuid.UUID,
    document_type: str,
    name: str,
    document_number: str | None = None,
    expiry_date: str | None = None,
    entity_name: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
    file_key: str | None = None,
) -> Document:
    """Create or update a document for the user."""
    # Resolve document type enum
    try:
        dt_enum = DocumentType(document_type)
    except ValueError:
        dt_enum = DocumentType.otro

    # Parse expiry date
    expiry = None
    if expiry_date:
        try:
            from datetime import date as date_type
            expiry = date_type.fromisoformat(expiry_date)
        except (ValueError, TypeError):
            pass

    # Check for existing document (same name + type)
    result = await session.execute(
        select(Document).where(
            Document.user_id == user_id,
            Document.document_type == dt_enum,
            Document.name == name,
            Document.deleted_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        logger.info("Updating existing document %s (%s)", existing.id, name)
        existing.document_number = document_number or existing.document_number
        existing.expiry_date = expiry or existing.expiry_date
        existing.entity_name = entity_name or existing.entity_name
        existing.notes = notes or existing.notes
        if file_key:
            existing.file_key = file_key
        if tags is not None:
            existing.tags = tags
        await session.flush()
        return existing

    doc = Document(
        user_id=user_id,
        document_type=dt_enum,
        name=name,
        document_number=document_number,
        expiry_date=expiry,
        entity_name=entity_name,
        notes=notes,
        tags=tags,
        file_key=file_key,
    )
    session.add(doc)
    await session.flush()
    logger.info("Created document %s: %s (%s)", doc.id, name, document_type)
    return doc


async def persist_event(
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    target_date: datetime | str,
    description: str | None = None,
    certainty: str = "certain",
    recurrence_rule: dict | None = None,
    asset_id: uuid.UUID | None = None,
) -> Event:
    """Create an event for the user."""
    # Parse date if string (supports ISO datetime with or without time).
    # All datetimes are stored in local Ecuador time (no TZ conversion needed).
    if isinstance(target_date, str):
        try:
            target_date = datetime.fromisoformat(target_date)
            # Keep as naive local time (Ecuador)
        except (ValueError, TypeError):
            target_date = datetime.now() + timedelta(days=1)  # default: tomorrow
    elif target_date is None:
        target_date = datetime.now() + timedelta(days=1)

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

    # Add items — skip duplicates (same content + pending in same list)
    # Fetch existing pending items in this list for dedup
    existing_result = await session.execute(
        select(ListItem).where(
            ListItem.list_id == lst.id,
            ListItem.status == ItemStatus.pending,
        )
    )
    existing_contents = {item.content.lower().strip() for item in existing_result.scalars().all()}

    created = []
    skipped = 0
    for item_text in items:
        content_clean = item_text.strip()
        if content_clean.lower() in existing_contents:
            skipped += 1
            continue

        item = ListItem(
            list_id=lst.id,
            content=content_clean,
            status=ItemStatus.pending,
            quantity=quantity,
        )
        session.add(item)
        created.append(item)
        existing_contents.add(content_clean.lower())  # Prevent duplicates within same batch

        # Generate embedding
        from app.services import embeddings as embed_svc
        embedding = await embed_svc.generate_embedding(content_clean)
        if embedding:
            item.embedding = embedding

    if skipped:
        logger.info("Skipped %d duplicate item(s) in list '%s'", skipped, list_name)

    await session.flush()
    if created:
        logger.info("Added %d items to list '%s'", len(created), list_name)
    return created


async def persist_note(
    session: AsyncSession,
    user_id: uuid.UUID,
    topic_name: str,
    content: str,
    source_message_id: uuid.UUID | None = None,
    file_key: str | None = None,
) -> Note:
    """Create a note under a topic. Creates the topic if it doesn't exist."""
    # Guard against null/empty topic names from extractor
    if not topic_name or not topic_name.strip():
        topic_name = "general"
    if not content or not content.strip():
        content = "(sin contenido)"

    # Embed file reference in content for searchability
    if file_key:
        content = f"[📸 foto: {file_key}] {content}"
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


# =============================================================================
# FINANCE — transactions and budgets
# =============================================================================

async def persist_transaction(
    session: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    amount: float,
    category: str,
    description: str | None = None,
    transaction_date: datetime | str | None = None,
    payment_method: str | None = None,
    notes: str | None = None,
) -> Transaction:
    """Create a transaction (expense or income)."""

    # Resolve type enum
    try:
        type_enum = TransactionType(type)
    except ValueError:
        type_enum = TransactionType.expense

    # Resolve category enum
    try:
        cat_enum = TransactionCategory(category)
    except ValueError:
        cat_enum = TransactionCategory.other_expense if type_enum == TransactionType.expense else TransactionCategory.other_income

    # Parse date
    if isinstance(transaction_date, str):
        try:
            transaction_date = datetime.fromisoformat(transaction_date)
        except (ValueError, TypeError):
            transaction_date = datetime.now()
    elif transaction_date is None:
        transaction_date = datetime.now()

    txn = Transaction(
        user_id=user_id,
        type=type_enum,
        amount=amount,
        category=cat_enum,
        description=description,
        transaction_date=transaction_date,
        payment_method=payment_method,
        notes=notes,
    )
    session.add(txn)
    await session.flush()
    logger.info("Created %s transaction %s: %.2f (%s)", type, txn.id, amount, category)
    return txn


async def persist_budget(
    session: AsyncSession,
    user_id: uuid.UUID,
    category: str,
    amount: float,
    period: str = "monthly",
    alert_threshold: int = 80,
) -> Budget:
    """Create or update a budget for a category."""
    from app.models.transaction import Budget

    # Resolve category
    try:
        cat_enum = TransactionCategory(category)
    except ValueError:
        raise ValueError(f"Invalid category: {category}")

    # Resolve period
    try:
        period_enum = BudgetPeriod(period)
    except ValueError:
        period_enum = BudgetPeriod.monthly

    # Check if active budget exists for this user+category
    result = await session.execute(
        select(Budget).where(
            Budget.user_id == user_id,
            Budget.category == cat_enum,
            Budget.is_active is True,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing
        existing.amount = amount
        existing.period = period_enum
        existing.alert_threshold = alert_threshold
        await session.flush()
        logger.info("Updated budget for user %s, category %s: %.2f", user_id, category, amount)
        return existing

    # Create new
    budget = Budget(
        user_id=user_id,
        category=cat_enum,
        amount=amount,
        period=period_enum,
        alert_threshold=alert_threshold,
    )
    session.add(budget)
    await session.flush()
    logger.info("Created budget for user %s, category %s: %.2f", user_id, category, amount)
    return budget
