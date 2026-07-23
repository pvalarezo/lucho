"""Shared base model with common columns.

All timestamps use local Ecuador time (America/Guayaquil).
The application NEVER uses UTC for data storage — this is a
non-negotiable architecture rule defined in AGENTS.md.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UUID

from app.database import Base  # noqa: F401 — re-exported via models.__init__


def now_ec() -> datetime:
    """Return current naive datetime in local Ecuador time (America/Guayaquil).

    The OS and PostgreSQL are configured for America/Guayaquil, so
    datetime.now() returns the correct local time without any timezone
    conversion.
    """
    return datetime.now()


class TimestampMixin:
    """Mixin that adds created_at / updated_at columns (naive local Ecuador time)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=now_ec, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=now_ec, onupdate=now_ec, nullable=False
    )


class UUIDMixin:
    """Mixin that adds a UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
