"""Subscription, Payment, and SubscriptionInvoice models — billing and SRI invoicing.

Design rules (spec section 9.5):
- subscriptions: user's plan, status, billing cycle
- payments: payment history with gateway reference
- subscription_invoices: SRI-compliant invoices via AuraFac
"""

import uuid as _uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, Float, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, TimestampMixin, Base, utcnow


class SubscriptionPlan(str, Enum):
    free = "free"
    individual = "individual"
    ruc = "ruc"


class SubscriptionStatus(str, Enum):
    active = "active"
    cancelled = "cancelled"
    expired = "expired"
    trial = "trial"


class PaymentStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"


class Subscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    plan: Mapped[SubscriptionPlan] = mapped_column(
        SAEnum(SubscriptionPlan, name="subscription_plan"),
        default=SubscriptionPlan.free,
        nullable=False,
    )

    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscription_status"),
        default=SubscriptionStatus.trial,
        nullable=False,
    )

    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = ()


class Payment(UUIDMixin, Base):
    __tablename__ = "payments"

    subscription_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False, index=True
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    gateway: Mapped[str] = mapped_column(String(32), nullable=False)  # "kushki", "payphone"
    gateway_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gateway_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.pending,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = ()


class SubscriptionInvoice(UUIDMixin, Base):
    __tablename__ = "subscription_invoices"

    payment_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, unique=True, index=True
    )

    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    sri_authorization: Mapped[str | None] = mapped_column(String(128), nullable=True)

    amount: Mapped[float] = mapped_column(Float, nullable=False)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = ()
