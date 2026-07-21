"""Internal test endpoints — not exposed publicly."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.database import async_session
from app.models.user import User
from app.models.event import Event, EventStatus, EventCertainty
from app.services.scheduler import schedule_event_reminder
from sqlalchemy import select

router = APIRouter(prefix="/internal", tags=["internal"])


class TestReminderRequest(BaseModel):
    whatsapp_id: str = "593993832368"
    title: str = "Prueba de recordatorio"
    minutes_from_now: int = 2


@router.post("/test-reminder")
async def test_ad_hoc_reminder(req: TestReminderRequest):
    """Schedule an ad-hoc reminder for testing.

    Creates an event and schedules a DateTrigger job
    to fire at now + minutes_from_now.
    """
    async with async_session() as session:
        # Find user
        result = await session.execute(
            select(User).where(User.whatsapp_id == req.whatsapp_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return {"error": f"User not found: {req.whatsapp_id}"}

        target = datetime.now(timezone.utc) + timedelta(minutes=req.minutes_from_now)

        event = Event(
            user_id=user.id,
            title=req.title,
            description=f"Recordatorio programado para {target.strftime('%H:%M:%S')} UTC",
            target_date=target,
            certainty=EventCertainty.certain,
            status=EventStatus.upcoming,
        )
        session.add(event)
        await session.flush()
        event_id = str(event.id)

        # Schedule the ad-hoc job in THIS process's scheduler (the API process)
        schedule_event_reminder(event_id, target)

        await session.commit()

        return {
            "ok": True,
            "event_id": event_id,
            "target_time": target.isoformat(),
            "seconds_from_now": req.minutes_from_now * 60,
            "message": f"Reminder scheduled for {target.strftime('%H:%M:%S')} UTC ({req.minutes_from_now} min from now)",
        }
