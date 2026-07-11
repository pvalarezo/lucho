"""Reminder model — when and how to notify, with audit trail.

One event can have multiple reminders (escalated: 15, 7, 3 days before).
Each reminder records the actual message sent and user response.
"""

import uuid as _uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, Base, utcnow

import enum


class ReminderChannel(str, enum.Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"


class ReminderStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    acknowledged = "acknowledged"  # user replied / read
    failed = "failed"


class Reminder(UUIDMixin, Base):
    __tablename__ = "reminders"

    event_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=False, index=True
    )

    days_before: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # e.g. 15, 7, 3, 0 (day of)

    channel: Mapped[ReminderChannel] = mapped_column(
        Enum(ReminderChannel, name="reminder_channel"),
        default=ReminderChannel.telegram,
        nullable=False,
    )

    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, name="reminder_status"),
        default=ReminderStatus.pending,
        nullable=False,
    )

    # Audit trail
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    message_text: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # exact message delivered
    user_response: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # user reply (if any)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    # Relationship
    event = relationship("Event", backref="reminders")
