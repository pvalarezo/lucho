"""Event model — what will happen and when (target_date, recurrence, status).

Design rules:
- target_date is a real indexed column — cron filters on it every day
- target_date is TIMESTAMP WITHOUT TIMEZONE — stored in local Ecuador time
- certainty: 'certain' (legal dates) or 'estimated' (maintenance, reminders)
- recurrence_rule as JSONB (RFC 5545 subset or simplified structure)
- status tracks lifecycle
"""

import uuid as _uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, TimestampMixin, Base, utcnow

import enum


class EventCertainty(str, enum.Enum):
    certain = "certain"       # known legal/contractual date
    estimated = "estimated"   # user's best guess, maintenance window


class EventStatus(str, enum.Enum):
    upcoming = "upcoming"
    done = "done"
    cancelled = "cancelled"
    overdue = "overdue"


class Event(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "events"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # Optional link to the asset this event belongs to
    asset_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    target_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )

    certainty: Mapped[EventCertainty] = mapped_column(
        Enum(EventCertainty, name="event_certainty"),
        default=EventCertainty.certain,
        nullable=False,
    )

    # Flexible recurrence (e.g. {"freq": "weekly", "days": [1,3,5]})
    recurrence_rule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status"),
        default=EventStatus.upcoming,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user = relationship("User", backref="events")
    asset = relationship("Asset", backref="events")
