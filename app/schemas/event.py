"""Pydantic schemas for Event and Reminder."""

import uuid
from datetime import date, datetime
from pydantic import BaseModel

from app.models.event import EventCertainty, EventStatus
from app.models.reminder import ReminderChannel, ReminderStatus


class EventCreate(BaseModel):
    asset_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    target_date: date
    certainty: EventCertainty = EventCertainty.certain
    recurrence_rule: dict | None = None


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    target_date: date | None = None
    certainty: EventCertainty | None = None
    recurrence_rule: dict | None = None
    status: EventStatus | None = None


class EventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    asset_id: uuid.UUID | None
    title: str
    description: str | None
    target_date: date
    certainty: EventCertainty
    recurrence_rule: dict | None
    status: EventStatus
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReminderRead(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    days_before: int
    channel: ReminderChannel
    status: ReminderStatus
    scheduled_for: datetime
    sent_at: datetime | None

    model_config = {"from_attributes": True}
