"""UserProfile model — additional data collected post-payment (1:1 with User)."""

import uuid as _uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, TimestampMixin, Base


class UserProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    full_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(32), nullable=True)  # cédula / RUC
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Accent preference: 'neutral', 'costeno', 'serrano', 'amazonico'
    accent: Mapped[str | None] = mapped_column(String(32), nullable=True, default='neutral')

    # Daily digest opt-in (default OFF — must be explicit per spec rule)
    daily_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    privacy_policy_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    privacy_policy_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    terms_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="profile")  # noqa: F821
