"""SQLAlchemy ORM models — all models must be imported here for Alembic autogenerate."""

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.user import User
from app.models.message import Message, MessageChannel, MessageType, MessageStatus
from app.models.asset import Asset, AssetType
from app.models.event import Event, EventCertainty, EventStatus
from app.models.reminder import Reminder, ReminderChannel, ReminderStatus

__all__ = [
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "User",
    "Message",
    "MessageChannel",
    "MessageType",
    "MessageStatus",
    "Asset",
    "AssetType",
    "Event",
    "EventCertainty",
    "EventStatus",
    "Reminder",
    "ReminderChannel",
    "ReminderStatus",
]
