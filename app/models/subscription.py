"""Subscription, Payment, and SubscriptionInvoice models — billing and SRI invoicing.

Design rules:
- subscription_plans: catalog of available plans with feature flags (JSONB)
- subscriptions: user's active plan, status, billing cycle, payment method
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


class PaymentMethod(str, Enum):
    credit_card = "credit_card"
    debit_card = "debit_card"
    deposit = "deposit"
    transfer = "transfer"
    cash = "cash"
    other = "other"


class RenewalType(str, Enum):
    monthly = "monthly"
    annual = "annual"


class Subscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    plan_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False, index=True
    )

    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscription_status"),
        default=SubscriptionStatus.trial,
        nullable=False,
    )

    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        SAEnum(PaymentMethod, name="payment_method"), nullable=True
    )
    renewal_type: Mapped[RenewalType | None] = mapped_column(
        SAEnum(RenewalType, name="renewal_type"), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscription")
    plan_ref: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="subscriptions")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="subscription")

    __table_args__ = ()


class Payment(UUIDMixin, Base):
    __tablename__ = "payments"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    subscription_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False, index=True
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        SAEnum(PaymentMethod, name="payment_method"),
        nullable=True,
    )

    gateway: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "kushki", "payphone"
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

    # Relationships
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="payments")

    __table_args__ = ()


class InvoiceStatus(str, Enum):
    issued = "issued"
    authorized = "authorized"
    cancelled = "cancelled"


class SubscriptionInvoice(UUIDMixin, Base):
    __tablename__ = "subscription_invoices"

    payment_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, unique=True, index=True
    )

    # ---- Invoice identification -------
    invoice_number: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )  # Sequential: 001-001-000000123

    # ---- Billing recipient (snapshot at issuance time) -------
    billing_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    billing_id_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    billing_id_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    billing_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    billing_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    billing_address: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # ---- Financial -------
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    # ---- SRI authorization -------
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoice_status"),
        default=InvoiceStatus.issued,
        nullable=False,
    )
    key49_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # Key49 document UUID for status polling
    sri_access_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # 48-digit SRI access key (generated by AuraFac)
    sri_authorization: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )  # SRI authorization number
    sri_authorization_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Timestamps -------
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = ()
