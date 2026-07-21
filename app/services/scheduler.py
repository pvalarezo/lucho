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
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.event import Event, EventStatus
from app.models.reminder import Reminder, ReminderChannel, ReminderStatus
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.list import ListItem, ItemStatus
from app.services import vehicle_rules as vr
from app.services.notifications import send_notification, NotificationChannel, resolve_user_contact
from app.services import telegram as telegram_svc
from app.services import whatsapp as whatsapp_svc
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
            await _evaluate_pico_y_placa(session)
            await _evaluate_budgets(session)
            await session.commit()
            logger.info("Daily reminder evaluation complete.")
        except Exception as exc:
            logger.exception("Daily reminder evaluation failed: %s", exc)
            await session.rollback()


# =============================================================================
# VEHICLE ASSETS — auto-create matriculación events
# =============================================================================

async def _evaluate_vehicle_assets(session: AsyncSession):
    """Evaluate matriculación, SOAT, RTV for all vehicle assets (from vehicles table)."""
    today = date.today()

    result = await session.execute(
        select(Vehicle).where(Vehicle.deleted_at.is_(None))
    )
    vehicles = result.scalars().all()

    for vehicle in vehicles:
        plate = vehicle.plate or ""
        last_digit = vehicle.last_digit

        if not plate and last_digit is None:
            continue

        rules = vr.evaluate_vehicle_rules(plate, last_digit, today)
        vehicle.last_digit = rules["last_digit"]
        vehicle.pico_y_placa_days = rules["pico_y_placa_days"]
        vehicle.next_matriculation = date.fromisoformat(rules["next_matriculation"])

        matric_date = date.fromisoformat(rules["next_matriculation"])
        await _ensure_event(
            session=session,
            user_id=vehicle.user_id,
            asset_id=vehicle.id,
            title=f"Matriculación {plate}",
            target_date=matric_date,
        )


# =============================================================================
# EVENTS — reminders (Telegram + WhatsApp template)
# =============================================================================

async def _evaluate_events(session: AsyncSession):
    """Check events due within reminder window and send notifications.

    Uses date-only comparison (ignoring time) for the day-based windows.
    Ad-hoc sub-day reminders ("avísame en 5 min") are handled by schedule_event_reminder().
    """
    today = date.today()
    window_end = today + timedelta(days=max(EVENT_WINDOWS))

    today_start = datetime.combine(today, datetime.min.time())
    window_end_dt = datetime.combine(window_end, datetime.max.time())

    result = await session.execute(
        select(Event).where(
            Event.status == EventStatus.upcoming,
            Event.target_date >= today_start,
            Event.target_date <= window_end_dt,
        )
    )
    events = result.scalars().all()

    for event in events:
        days_until = (event.target_date.date() - today).days
        for window in EVENT_WINDOWS:
            if days_until == window:
                # Guard: avoid sending duplicate reminders for the same event+window
                dupe = await session.execute(
                    select(Reminder).where(
                        Reminder.event_id == event.id,
                        Reminder.days_before == window,
                    )
                )
                if dupe.scalar_one_or_none():
                    continue

                await _send_event_reminder(session, event, days_until)

                # Record in reminders table for idempotency
                reminder = Reminder(
                    event_id=event.id,
                    days_before=window,
                    channel=ReminderChannel.telegram,
                    status=ReminderStatus.sent,
                    scheduled_for=event.target_date - timedelta(days=window),
                )
                session.add(reminder)
                break  # one reminder per event per day


async def _send_event_reminder(
    session: AsyncSession,
    event: Event,
    days_until: int,
):
    """Send an event reminder to the user (Telegram + WhatsApp template)."""
    user_result = await session.execute(
        select(User).where(User.id == event.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return

    contact_id, channel = await resolve_user_contact(user)
    if not contact_id:
        return

    emoji = "🔴" if days_until == 0 else "🟡" if days_until <= 3 else "🟢"
    ds = "HOY" if days_until == 0 else f"mañana" if days_until == 1 else f"en {days_until} días"

    # Format datetime nicely: show time only if it's not midnight
    target = event.target_date
    if target.hour == 0 and target.minute == 0:
        date_str = target.strftime("%Y-%m-%d")
    else:
        date_str = target.strftime("%Y-%m-%d %H:%M")
        ds = f"{ds} a las {target.strftime('%H:%M')}" if days_until <= 0 else ds

    msg = (
        f"{emoji} *Recordatorio de evento*\n\n"
        f"📌 *{event.title}*\n"
    )
    if event.description:
        msg += f"📝 {event.description}\n"
    msg += f"📅 Fecha: {ds} ({date_str})\n\n"
    msg += "Si ya pasó o querés cambiarlo, decime y lo actualizo."

    sent = await send_notification(
        user_id=str(event.user_id),
        contact_id=contact_id,
        message=msg,
        channel=channel,
    )
    if sent:
        logger.info("Event reminder sent: %s (%d days)", event.title, days_until)

    # WhatsApp template (for proactive reminders outside 24h window)
    if user.whatsapp_id:
        await _send_event_reminder_whatsapp(
            user.whatsapp_id, emoji, event.title, ds, date_str
        )


async def _send_event_reminder_whatsapp(
    phone: str,
    emoji: str,
    event_title: str,
    days_text: str,
    target_date_str: str,
):
    """Send event reminder via WhatsApp template (5 body params)."""
    await whatsapp_svc.send_template_message(
        phone=phone,
        template_name="event_reminder",
        language_code="es",
        body_params=[emoji, event_title, days_text, target_date_str, event_title],
    )


# =============================================================================
# AD-HOC EVENT REMINDER — "avísame en 5 minutos"
# =============================================================================

async def _ad_hoc_event_reminder(event_id_str: str):
    """One-shot job: load event from DB and send reminder at exact time.

    Scheduled via DateTrigger when an event is created with a specific time.
    """
    import uuid as _uuid

    async with async_session() as session:
        try:
            result = await session.execute(
                select(Event).where(Event.id == _uuid.UUID(event_id_str))
            )
            event = result.scalar_one_or_none()
            if not event or event.status != EventStatus.upcoming:
                logger.info("Ad-hoc event reminder skipped: event %s not found or not upcoming", event_id_str)
                return

            today = date.today()
            days_until = (event.target_date.date() - today).days
            days_until = max(days_until, 0)  # clamp: if time already passed, treat as today

            await _send_event_reminder(session, event, days_until)
            logger.info("Ad-hoc event reminder sent: %s", event.title)

        except Exception as exc:
            logger.exception("Ad-hoc event reminder failed for event %s: %s", event_id_str, exc)


def schedule_event_reminder(event_id: str, target_datetime: datetime):
    """Schedule a one-shot reminder for an event at its exact target_datetime.

    Called from handle_save_event() when the user specifies a time
    (e.g., "recuérdame la reunión a las 3pm" or "avísame en 5 minutos").

    The daily 8AM cron handles day-level reminders (15/7/3/0 days before).
    This function handles sub-day precision.

    All times are in local Ecuador time (system timezone).
    """
    # Don't schedule if already in the past
    now = datetime.now()
    if target_datetime <= now:
        logger.warning("Skipping ad-hoc reminder for event %s: target time already passed (%s)", event_id, target_datetime)
        return

    job_id = f"event_ad_hoc_{event_id}"

    # Remove existing job for this event if any (e.g., event was updated)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        _ad_hoc_event_reminder,
        trigger=DateTrigger(run_date=target_datetime),
        args=[event_id],
        id=job_id,
        name=f"Ad-hoc reminder: event {event_id}",
        replace_existing=True,
    )
    logger.info("Scheduled ad-hoc reminder for event %s at %s", event_id, target_datetime.isoformat())


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

    result = await session.execute(
        select(Document).where(
            Document.deleted_at.is_(None),
            Document.expiry_date.isnot(None),
            Document.expiry_date >= today,
            Document.expiry_date <= window_end,
        )
    )
    docs = result.scalars().all()

    for doc in docs:
        days_until = (doc.expiry_date - today).days

        for window in DOCUMENT_WINDOWS:
            if days_until == window:
                await _send_document_reminder(session, doc, days_until)
                break


async def _send_document_reminder(
    session: AsyncSession,
    doc: Document,
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

    doc_type = doc.document_type.value if doc.document_type else "documento"
    doc_name = doc.name
    expiry_date = doc.expiry_date
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

    # WhatsApp template (for proactive reminders outside 24h window)
    if user.whatsapp_id:
        await _send_document_reminder_whatsapp(
            user.whatsapp_id, emoji, doc_name, doc_type, ds, str(expiry_date)
        )


async def _send_document_reminder_whatsapp(
    phone: str,
    emoji: str,
    doc_name: str,
    doc_type: str,
    days_text: str,
    expiry_date_str: str,
):
    """Send document reminder via WhatsApp template (6 body params)."""
    await whatsapp_svc.send_template_message(
        phone=phone,
        template_name="document_reminder",
        language_code="es",
        body_params=[emoji, doc_name, doc_type, days_text, expiry_date_str, doc_name],
    )


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

    # WhatsApp template (for proactive reminders outside 24h window)
    if user.whatsapp_id:
        await _send_project_reminder_whatsapp(
            user.whatsapp_id, emoji, project.name, task.content,
            ds, str(task.due_date)
        )


async def _send_project_reminder_whatsapp(
    phone: str,
    emoji: str,
    project_name: str,
    task_content: str,
    days_text: str,
    due_date_str: str,
):
    """Send project reminder via WhatsApp template (6 body params)."""
    await whatsapp_svc.send_template_message(
        phone=phone,
        template_name="project_reminder",
        language_code="en",  # TODO: revert to "es" when Spanish translation is approved
        body_params=[emoji, project_name, task_content, days_text, due_date_str, task_content],
    )


# =============================================================================
# PICO Y PLACA — daily restriction check
# =============================================================================

async def _evaluate_pico_y_placa(session: AsyncSession):
    """Check vehicles with pico y placa today and notify via WhatsApp template."""
    today = date.today()
    weekday_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    today_name = weekday_names[today.weekday()]

    # No restrictions on weekends
    if today.weekday() >= 5:
        return

    result = await session.execute(
        select(Vehicle).where(Vehicle.deleted_at.is_(None))
    )
    vehicles = result.scalars().all()

    for vehicle in vehicles:
        plate = vehicle.plate or ""
        pyp_days = vehicle.pico_y_placa_days or ""

        if not plate or not pyp_days or today_name not in pyp_days:
            continue

        user_result = await session.execute(
            select(User).where(User.id == vehicle.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user or not user.whatsapp_id:
            continue

        await whatsapp_svc.send_template_message(
            phone=user.whatsapp_id,
            template_name="pico_y_placa",
            language_code="es",
            body_params=[plate, f"hoy {today_name.lower()}"],
        )
        logger.info("Pico y placa reminder sent: %s on %s", plate, today_name)


# =============================================================================
# BUDGET ALERTS
# =============================================================================

async def _evaluate_budgets(session: AsyncSession):
    """Check budgets and alert users who are near or over their spending limits."""
    from datetime import date, datetime
    from app.models.transaction import Budget, Transaction, TransactionType, TransactionCategory

    today = date.today()
    start = datetime.combine(today.replace(day=1), datetime.min.time())
    end = datetime.combine(today, datetime.max.time())

    result = await session.execute(
        select(Budget).where(Budget.is_active == True)
    )
    budgets = result.scalars().all()

    for budget in budgets:
        # Get spending for this category this month
        spent_result = await session.execute(
            select(func.sum(Transaction.amount))
            .where(
                Transaction.user_id == budget.user_id,
                Transaction.type == TransactionType.expense,
                Transaction.category == budget.category,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
            )
        )
        spent = float(spent_result.scalar_one() or 0)

        if float(budget.amount) == 0:
            continue

        percentage = round((spent / float(budget.amount)) * 100)

        # Only alert if threshold reached
        if percentage < budget.alert_threshold:
            continue

        # Check if already alerted today (stored in attributes)
        attrs = budget.attributes or {}
        last_alert_date = attrs.get("last_alert_date")
        if last_alert_date == today.isoformat():
            continue

        # Load user
        user_result = await session.execute(
            select(User).where(User.id == budget.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            continue

        contact_id, channel = await resolve_user_contact(user)
        if not contact_id:
            continue

        cat_label = budget.category.value.replace("_", " ").title()
        remaining = max(float(budget.amount) - spent, 0)
        emoji = "🔴" if percentage >= 100 else "⚠️"

        msg = (
            f"{emoji} *Alerta de presupuesto*\n\n"
            f"📊 {cat_label}: ${spent:.0f} de ${float(budget.amount):.0f} ({percentage}%)\n"
            f"{'🚫 Ya te pasaste del presupuesto.' if percentage >= 100 else f'Te quedan ${remaining:.0f}.'}\n\n"
            f"¿Querés ajustar el presupuesto o revisar tus gastos?"
        )

        sent = await send_notification(
            user_id=str(budget.user_id),
            contact_id=contact_id,
            message=msg,
            channel=channel,
        )
        if sent:
            logger.info("Budget alert sent: %s for %s (%d%%)", 
                       cat_label, budget.user_id, percentage)
            # Mark alerted
            if not budget.attributes:
                budget.attributes = {}
            budget.attributes["last_alert_date"] = today.isoformat()


# =============================================================================
# HELPERS
# =============================================================================

async def _ensure_event(session, user_id, asset_id, title, target_date, certainty="certain"):
    """Create an event if one doesn't already exist for this title + date."""
    target_day = target_date.date() if isinstance(target_date, datetime) else target_date
    target_day_start = datetime.combine(target_day, datetime.min.time())

    result = await session.execute(
        select(Event).where(
            Event.user_id == user_id,
            Event.asset_id == asset_id,
            Event.title == title,
            Event.target_date >= target_day_start,
            Event.target_date < target_day_start + timedelta(days=1),
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
        target_date=target_day_start,
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
    """Send a morning summary to users with active data (Telegram + WhatsApp)."""
    logger.info("Starting daily digest...")
    today = date.today()
    weekday = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"][today.weekday()]

    async with async_session() as session:
        try:
            result = await session.execute(
                select(User).where(User.is_active == True)
            )
            users = result.scalars().all()

            for user in users:
                digest = await _build_digest(session, user, today, weekday)
                if not digest:
                    continue

                # Telegram
                if user.telegram_id:
                    try:
                        await telegram_svc.send_message(int(user.telegram_id), digest)
                        logger.info("Digest sent to Telegram %s", user.telegram_id)
                    except Exception as exc:
                        logger.warning("Digest Telegram failed for %s: %s", user.telegram_id, exc)

                # WhatsApp template
                if user.whatsapp_id:
                    try:
                        await whatsapp_svc.send_template_message(
                            phone=user.whatsapp_id,
                            template_name="daily_digest",
                            language_code="es",
                            body_params=[digest],
                        )
                        logger.info("Digest sent to WhatsApp %s", user.whatsapp_id)
                    except Exception as exc:
                        logger.warning("Digest WhatsApp failed for %s: %s", user.whatsapp_id, exc)

            await session.commit()
        except Exception as exc:
            logger.exception("Daily digest failed: %s", exc)
            await session.rollback()


async def _build_digest(session, user, today, weekday):
    """Build a natural-language morning digest using the agent."""
    from app.agent import process_message

    # Vehicles
    result = await session.execute(
        select(Vehicle).where(
            Vehicle.user_id == user.id,
            Vehicle.deleted_at.is_(None),
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
    today_start = datetime.combine(today, datetime.min.time())
    until_end = datetime.combine(until, datetime.max.time())
    result = await session.execute(
        select(Event).where(
            Event.user_id == user.id,
            Event.status == EventStatus.upcoming,
            Event.target_date >= today_start,
            Event.target_date <= until_end,
        ).order_by(Event.target_date)
    )
    deadlines = result.scalars().all()

    # Document expiries next 30 days
    doc_until = today + timedelta(days=30)
    result = await session.execute(
        select(Document).where(
            Document.user_id == user.id,
            Document.expiry_date.isnot(None),
            Document.expiry_date >= today,
            Document.expiry_date <= doc_until,
            Document.deleted_at.is_(None),
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
            plate = v.plate or "?"
            pyp = v.pico_y_placa_days or ""
            if pyp:
                parts.append(f"  • {plate}: pico y placa {pyp}")
                if weekday.capitalize() in pyp:
                    parts.append("    ⚠️ HOY tiene pico y placa")

    if deadlines:
        parts.append("\n📅 Próximos 7 días:")
        for d in deadlines:
            days_left = (d.target_date.date() - today).days
            emoji = "🔴" if days_left == 0 else "🟡" if days_left <= 3 else "🟢"
            date_label = d.target_date.strftime("%Y-%m-%d")
            if d.target_date.hour != 0 or d.target_date.minute != 0:
                date_label += f" {d.target_date.strftime('%H:%M')}"
            ds = "HOY" if days_left == 0 else f"{date_label} ({days_left} días)"
            parts.append(f"  {emoji} {d.title}: {ds}")

    if docs:
        doc_warnings = []
        for d in docs:
            if d.expiry_date:
                days_left = (d.expiry_date - today).days
                doc_warnings.append(f"  📄 {d.name}: vence {d.expiry_date} ({days_left} días)")
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
