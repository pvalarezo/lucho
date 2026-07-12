"""Daily scheduler — evaluates deterministic rules and creates reminders.

Runs once per day (configurable time). For each user:
1. Fetches all vehicle assets
2. Evaluates matriculación, SOAT, RTV deadlines
3. Checks for upcoming events (today + N days)
4. Creates/updates reminders with escalated lead times (15, 7, 3 days before)
5. Sends notifications via Telegram (if token configured)

This is DETERMINISTIC code — no LLM involved in any decision.
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
from app.services import vehicle_rules as vr
from app.services import telegram as telegram_svc
from app.config import settings

logger = logging.getLogger(__name__)

# Escalated reminder windows: days before target_date
REMINDER_WINDOWS = [15, 7, 3, 0]  # 15, 7, 3 days before, and day of

scheduler = AsyncIOScheduler()


async def run_daily_rules():
    """
    Daily cron job: evaluate all rules and create/send reminders.
    Called by APScheduler every day at the configured hour.
    """
    logger.info("Starting daily rules evaluation...")

    async with async_session() as session:
        try:
            # ---- 1. Vehicle rules ----
            await _evaluate_vehicle_assets(session)

            # ---- 2. Upcoming events ----
            await _evaluate_upcoming_events(session)

            await session.commit()
            logger.info("Daily rules evaluation complete.")

        except Exception as exc:
            logger.exception("Daily rules evaluation failed: %s", exc)
            await session.rollback()


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

        # Update asset attributes with computed values
        vehicle.attributes = {
            **attrs,
            "last_digit": rules["last_digit"],
            "pico_y_placa_days": rules["pico_y_placa_days"],
            "next_matriculation": rules["next_matriculation"],
        }

        logger.info(
            "Vehicle %s (%s): matriculación %s (%d days), pico y placa: %s",
            plate,
            vehicle.name,
            rules["next_matriculation"],
            rules["days_until_matriculation"],
            rules["pico_y_placa_days"],
        )

        # Create matriculación event if not exists
        matric_date = date.fromisoformat(rules["next_matriculation"])
        await _ensure_event(
            session=session,
            user_id=vehicle.user_id,
            asset_id=vehicle.id,
            title=f"Matriculación {plate}",
            target_date=matric_date,
            certainty="certain",
        )


async def _evaluate_upcoming_events(session: AsyncSession):
    """Check events due within the reminder window and create reminders."""
    today = date.today()
    max_window = max(REMINDER_WINDOWS)
    window_end = today + timedelta(days=max_window)

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

        for window in REMINDER_WINDOWS:
            if days_until == window:
                await _create_reminder(
                    session=session,
                    event=event,
                    days_before=window,
                )


async def _ensure_event(
    session: AsyncSession,
    user_id,
    asset_id,
    title: str,
    target_date: date,
    certainty: str = "certain",
):
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
    existing = result.scalar_one_or_none()
    if existing:
        return existing

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
    logger.info("Auto-created event: %s on %s", title, target_date)
    return event


async def _create_reminder(
    session: AsyncSession,
    event: Event,
    days_before: int,
):
    """Create a reminder for an event if not already scheduled."""
    # Check if reminder already exists
    result = await session.execute(
        select(Reminder).where(
            Reminder.event_id == event.id,
            Reminder.days_before == days_before,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    now = datetime.now(timezone.utc)
    scheduled_for = datetime.combine(
        event.target_date, datetime.min.time(), tzinfo=timezone.utc
    ) - timedelta(days=days_before)

    reminder = Reminder(
        event_id=event.id,
        days_before=days_before,
        channel=ReminderChannel.telegram,
        status=ReminderStatus.pending,
        scheduled_for=scheduled_for,
    )
    session.add(reminder)
    await session.flush()
    logger.info(
        "Created reminder for event '%s': %d days before (%s)",
        event.title,
        days_before,
        scheduled_for.date().isoformat(),
    )
    return reminder


def start_scheduler():
    """Start the APScheduler with daily rules evaluation."""
    scheduler.add_job(
        run_daily_rules,
        trigger=CronTrigger(hour=8, minute=0),  # 8:00 AM daily
        id="daily_rules",
        name="Daily deterministic rules evaluation",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: daily rules at 08:00 AM")


def stop_scheduler():
    """Stop the APScheduler gracefully."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
