"""Daily scheduler — unified reminder engine.

Evaluates all entities with dates and sends reminders through
the notification service (channel-agnostic: Telegram, WhatsApp, etc.).

Entity types and their reminder windows:
- Documents (SOAT, cédula, pasaporte): 30, 15, 7 days — critical
- Events (citas, reuniones): 15, 7, 3, 0 days — personal planning
- Project tasks: 7, 3, 1 days — operational
- Vehicle assets: auto-creates events → handled by event reminders

ALL deterministic — no LLM involved in any decision.
"""

import asyncio
import logging
from datetime import date, datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.asset import Asset, AssetType
from app.models.event import Event, EventStatus
from app.models.reminder import Reminder, ReminderChannel, ReminderStatus
from app.models.user import User
from app.models.list import ListItem, ItemStatus
from app.services import vehicle_rules as vr
from app.services.notifications import send_notification, NotificationChannel, resolve_user_contact
from app.services import telegram as telegram_svc
from app.config import settings

logger = logging.getLogger(__name__)

# ---- Reminder windows by entity type ----
# (days before target_date when reminders are sent)

EVENT_WINDOWS = [15, 7, 3, 0]
DOCUMENT_WINDOWS = [30, 15, 7]
PROJECT_WINDOWS = [7, 3, 1]

scheduler = AsyncIOScheduler()


# =============================================================================
# MAIN DAILY JOB
# =============================================================================

async def run_daily_rules():
    """Daily cron: evaluate all entities and send reminders."""
    logger.info("Starting daily reminder evaluation...")

    async with async_session() as session:
        try:
            await _evaluate_vehicle_assets(session)
            await _evaluate_events(session)
            await _evaluate_documents(session)
            await _evaluate_project_tasks(session)
            await session.commit()
            logger.info("Daily reminder evaluation complete.")
        except Exception as exc:
            logger.exception("Daily reminder evaluation failed: %s", exc)
            await session.rollback()


# =============================================================================
# VEHICLE ASSETS — auto-create matriculación events
# =============================================================================

async def _evaluate_vehicle_assets(session: AsyncSession):
    """Evaluate matriculación, SOAT, RTV for all vehicle assets."""
    today = date.today()

    result = await session.execute(
        select(Asset).where(
            Asset.asset_type == AssetType.vehicle,
            Asset.deleted_at.is_(None),
        )
    )
    vehicles = result.scalars().all()

    for vehicle in vehicles:
        attrs = vehicle.attributes or {}
        plate = attrs.get("plate", "")
        last_digit = attrs.get("last_digit")

        if not plate and last_digit is None:
            continue

        rules = vr.evaluate_vehicle_rules(plate, last_digit, today)
        vehicle.attributes = {**attrs, **{
            "last_digit": rules["last_digit"],
            "pico_y_placa_days": rules["pico_y_placa_days"],
            "next_matriculation": rules["next_matriculation"],
        }}

        matric_date = date.fromisoformat(rules["next_matriculation"])
        await _ensure_event(
            session=session,
            user_id=vehicle.user_id,
            asset_id=vehicle.id,
            title=f"Matriculación {plate}",
            target_date=matric_date,
        )


# =============================================================================
# EVENTS — reminders via reminders table
# =============================================================================

async def _evaluate_events(session: AsyncSession):
    """Check events due within reminder window and create reminders."""
    today = date.today()
    window_end = today + timedelta(days=max(EVENT_WINDOWS))

    result = await session.execute(
        select(Event).where(
            Event.status == EventStatus.upcoming,
            Event.target_date >= today,
            Event.target_date <= window_end,
        )
    )
    events = result.scalars().all()

    for event in events:
        days_until = (event.target_date - today).days
        for window in EVENT_WINDOWS:
            if days_until == window:
                await _create_reminder(session, event, days_before=window)


async def _create_reminder(session: AsyncSession, event: Event, days_before: int):
    """Create a reminder for an event if not already scheduled."""
    result = await session.execute(
        select(Reminder).where(
            Reminder.event_id == event.id,
            Reminder.days_before == days_before,
        )
    )
    if result.scalar_one_or_none():
        return

    reminder = Reminder(
        event_id=event.id,
        days_before=days_before,
        channel=ReminderChannel.telegram,
        status=ReminderStatus.pending,
        scheduled_for=datetime.combine(
            event.target_date, datetime.min.time(), tzinfo=timezone.utc
        ) - timedelta(days=days_before),
    )
    session.add(reminder)


# =============================================================================
# DOCUMENTS — expiry date reminders
# =============================================================================

async def _evaluate_documents(session: AsyncSession):
    """
    Check documents with expiry_date and send reminders.
    Documents: SOAT, cédula, pasaporte, licencia, garantía.
    Reminder windows: 30, 15, 7 days before expiry.
    """
    today = date.today()
    window_end = today + timedelta(days=max(DOCUMENT_WINDOWS))

    # Get all document-type assets
    result = await session.execute(
        select(Asset).where(
            Asset.asset_type == AssetType.document,
            Asset.deleted_at.is_(None),
        )
    )
    docs = result.scalars().all()

    for doc in docs:
        attrs = doc.attributes or {}
        expiry_str = attrs.get("expiry_date") or attrs.get("expiration_date")
        if not expiry_str:
            continue

        try:
            expiry_date = date.fromisoformat(expiry_str)
        except (ValueError, TypeError):
            continue

        days_until = (expiry_date - today).days

        for window in DOCUMENT_WINDOWS:
            if days_until == window:
                await _send_document_reminder(session, doc, attrs, expiry_date, days_until)
                break  # one reminder per document per day


async def _send_document_reminder(
    session: AsyncSession,
    doc: Asset,
    attrs: dict,
    expiry_date: date,
    days_until: int,
):
    """Send a document expiry reminder to the user."""
    user_result = await session.execute(
        select(User).where(User.id == doc.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return

    contact_id, channel = await resolve_user_contact(user)
    if not contact_id:
        return

    doc_type = attrs.get("document_type", "documento")
    doc_name = doc.name
    emoji = "🔴" if days_until <= 7 else "🟡" if days_until <= 15 else "🟢"
    ds = "HOY" if days_until == 0 else f"mañana" if days_until == 1 else f"en {days_until} días"

    msg = (
        f"{emoji} *Recordatorio de documento*\n\n"
        f"📄 *{doc_name}* ({doc_type})\n"
        f"📅 Vence: {ds} ({expiry_date})\n\n"
        f"Si ya lo renovaste, decime 'ya renové {doc_name}' y lo actualizo."
    )

    sent = await send_notification(
        user_id=str(doc.user_id),
        contact_id=contact_id,
        message=msg,
        channel=channel,
    )
    if sent:
        logger.info("Document reminder sent: %s (%d days)", doc_name, days_until)


# =============================================================================
# PROJECT TASKS — due date reminders
# =============================================================================

async def _evaluate_project_tasks(session: AsyncSession):
    """Check project tasks with due dates and send reminders."""
    from app.models.project import ProjectTask, TaskStatus, Project

    today = date.today()
    window_end = today + timedelta(days=max(PROJECT_WINDOWS))

    result = await session.execute(
        select(ProjectTask, Project).join(
            Project, ProjectTask.project_id == Project.id
        ).where(
            ProjectTask.status == TaskStatus.pending,
            ProjectTask.due_date.isnot(None),
            ProjectTask.due_date >= today,
            ProjectTask.due_date <= window_end,
            ProjectTask.reminder_sent == False,
        )
    )
    tasks = result.all()

    for task, project in tasks:
        days_until = (task.due_date - today).days

        for window in PROJECT_WINDOWS:
            if days_until == window:
                await _send_project_reminder(session, project, task, days_until)
                break

        # Mark reminded on due date
        if days_until == 0:
            task.reminder_sent = True


async def _send_project_reminder(
    session: AsyncSession,
    project,
    task,
    days_until: int,
):
    """Send a project task reminder to the user."""
    user_result = await session.execute(
        select(User).where(User.id == project.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return

    contact_id, channel = await resolve_user_contact(user)
    if not contact_id:
        return

    emoji = "🔴" if days_until <= 1 else "🟡" if days_until <= 3 else "🟢"
    ds = "HOY" if days_until == 0 else f"mañana" if days_until == 1 else f"en {days_until} días"

    msg = (
        f"{emoji} *Recordatorio de proyecto*\n\n"
        f"📋 Proyecto: *{project.name}*\n"
        f"📝 Tarea: {task.content}\n"
        f"📅 Vence: {ds} ({task.due_date})\n\n"
        f"Cuando la termines, decime 'completé {task.content[:40]}'."
    )

    sent = await send_notification(
        user_id=str(project.user_id),
        contact_id=contact_id,
        message=msg,
        channel=channel,
    )
    if sent:
        logger.info("Project reminder sent: %s (%d days)", task.content[:50], days_until)


# =============================================================================
# HELPERS
# =============================================================================

async def _ensure_event(session, user_id, asset_id, title, target_date, certainty="certain"):
    """Create an event if one doesn't already exist for this title + date."""
    result = await session.execute(
        select(Event).where(
            Event.user_id == user_id,
            Event.asset_id == asset_id,
            Event.title == title,
            Event.target_date == target_date,
            Event.status == EventStatus.upcoming,
        )
    )
    if result.scalar_one_or_none():
        return

    from app.models.event import EventCertainty
    try:
        cert = EventCertainty(certainty)
    except ValueError:
        cert = EventCertainty.certain

    event = Event(
        user_id=user_id,
        asset_id=asset_id,
        title=title,
        target_date=target_date,
        certainty=cert,
        status=EventStatus.upcoming,
    )
    session.add(event)
    await session.flush()
    return event


# =============================================================================
# DAILY DIGEST
# =============================================================================

async def run_daily_digest():
    """Send a morning summary to users with active data."""
    logger.info("Starting daily digest...")
    today = date.today()
    weekday = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"][today.weekday()]

    async with async_session() as session:
        try:
            result = await session.execute(
                select(User).where(User.telegram_id.isnot(None), User.is_active == True)
            )
            users = result.scalars().all()

            for user in users:
                digest = await _build_digest(session, user, today, weekday)
                if digest:
                    try:
                        await telegram_svc.send_message(int(user.telegram_id), digest)
                    except Exception as exc:
                        logger.warning("Digest failed for %s: %s", user.telegram_id, exc)

            await session.commit()
        except Exception as exc:
            logger.exception("Daily digest failed: %s", exc)
            await session.rollback()


async def _build_digest(session, user, today, weekday):
    """Build a natural-language morning digest using the agent."""
    from app.agent import process_message

    # Vehicles
    result = await session.execute(
        select(Asset).where(
            Asset.user_id == user.id,
            Asset.asset_type == AssetType.vehicle,
            Asset.deleted_at.is_(None),
        )
    )
    vehicles = result.scalars().all()

    # Pending items
    result = await session.execute(
        select(ListItem).join(ListItem.list).where(
            ListItem.list.has(user_id=user.id),
            ListItem.status == ItemStatus.pending,
        ).order_by(ListItem.created_at).limit(10)
    )
    pending = result.scalars().all()

    # Deadlines next 7 days
    until = today + timedelta(days=7)
    result = await session.execute(
        select(Event).where(
            Event.user_id == user.id,
            Event.status == EventStatus.upcoming,
            Event.target_date >= today,
            Event.target_date <= until,
        ).order_by(Event.target_date)
    )
    deadlines = result.scalars().all()

    # Document expiries next 30 days
    doc_until = today + timedelta(days=30)
    result = await session.execute(
        select(Asset).where(
            Asset.user_id == user.id,
            Asset.asset_type == AssetType.document,
            Asset.deleted_at.is_(None),
        )
    )
    docs = result.scalars().all()

    if not vehicles and not pending and not deadlines and not docs:
        return None

    parts = [
        f"Hoy es {weekday} {today.strftime('%d de %B de %Y')}.",
        "Generá un resumen matutino breve y cálido en español ecuatoriano.",
    ]

    if vehicles:
        parts.append("\n🚗 Vehículos:")
        for v in vehicles:
            attrs = v.attributes or {}
            plate = attrs.get("plate", "?")
            pyp = attrs.get("pico_y_placa_days", "")
            if pyp:
                parts.append(f"  • {plate}: pico y placa {pyp}")
                if weekday.capitalize() in pyp:
                    parts.append("    ⚠️ HOY tiene pico y placa")

    if deadlines:
        parts.append("\n📅 Próximos 7 días:")
        for d in deadlines:
            days_left = (d.target_date - today).days
            emoji = "🔴" if days_left == 0 else "🟡" if days_left <= 3 else "🟢"
            ds = "HOY" if days_left == 0 else f"{d.target_date} ({days_left} días)"
            parts.append(f"  {emoji} {d.title}: {ds}")

    if docs:
        doc_warnings = []
        for d in docs:
            attrs = d.attributes or {}
            exp = attrs.get("expiry_date") or attrs.get("expiration_date")
            if exp:
                try:
                    exp_date = date.fromisoformat(exp)
                    days_left = (exp_date - today).days
                    if days_left <= 30:
                        doc_warnings.append(f"  📄 {d.name}: vence {exp_date} ({days_left} días)")
                except (ValueError, TypeError):
                    pass
        if doc_warnings:
            parts.append("\n📄 Documentos por vencer:")
            parts.extend(doc_warnings[:5])

    if pending:
        parts.append("\n📝 Pendientes:")
        for p in pending[:8]:
            parts.append(f"  • {p.content}")

    parts.append("\nEscribí el saludo de buenos días con el resumen. Sé breve, cálido, ecuatoriano.")

    try:
        result = await process_message(
            session=session,
            user_id=str(user.id),
            user_message="\n".join(parts),
        )
        return result.get("text", "") if isinstance(result, dict) else result
    except Exception as exc:
        logger.error("Digest agent failed: %s", exc)
        return None


# =============================================================================
# SCHEDULER LIFECYCLE
# =============================================================================

def start_scheduler():
    """Start APScheduler with daily reminder evaluation and digest."""
    scheduler.add_job(
        run_daily_rules,
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_rules",
        name="Daily reminder evaluation (all entities)",
        replace_existing=True,
    )
    scheduler.add_job(
        run_daily_digest,
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_digest",
        name="Daily morning digest",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: unified reminders + digest at 08:00 AM")


def stop_scheduler():
    """Stop the APScheduler gracefully."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
