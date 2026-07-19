"""SubscriptionPlan model — catalog of available plans with feature flags."""

import uuid as _uuid

from sqlalchemy import String, Float, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, TimestampMixin, Base


class SubscriptionPlan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscription_plans"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)

    price_monthly_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    price_annual_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)

    # JSONB with feature flags, e.g.:
    # {"vehicles": true, "documents": true, "events": true, "file_storage_mb": 100, ...}
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Reverse relationship
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="plan_ref"
    )
