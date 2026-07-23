"""Billing models — clients, products, quotes, and line items.

Fase 0: Cotizaciones (quotes) — no SRI, no Key49.
Fase 1 (futuro): Facturación electrónica vía Key49.

IVA: configurable via BusinessInfo.iva_rate (not hardcoded).
"""

import uuid as _uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import String, Float, Date, DateTime, Boolean, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, TimestampMixin, Base, utcnow


# ---- ENUMs ----

class BillingIdType(str, Enum):
    cedula = "cedula"
    ruc = "ruc"
    pasaporte = "pasaporte"
    consumidor_final = "consumidor_final"


class BillingDocumentType(str, Enum):
    quote = "quote"
    # invoice = "invoice"  # Fase 1


class BillingDocumentStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"


# ---- Models ----

class BillingClient(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "billing_clients"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    id_type: Mapped[BillingIdType] = mapped_column(
        SAEnum(BillingIdType, name="billing_id_type"),
        default=BillingIdType.cedula,
        nullable=False,
    )
    id_number: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", backref="billing_clients")


class BillingProduct(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "billing_products"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    has_iva: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(16), default="UNIDAD", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user = relationship("User", backref="billing_products")


class BillingDocument(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "billing_documents"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    client_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_clients.id"), nullable=True
    )

    # Client snapshot (even if client is from catalog)
    client_name: Mapped[str] = mapped_column(String(256), nullable=False)
    client_id_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    document_type: Mapped[BillingDocumentType] = mapped_column(
        SAEnum(BillingDocumentType, name="billing_document_type"),
        default=BillingDocumentType.quote,
        nullable=False,
    )

    quote_number: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True
    )  # COT-0001

    issue_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    subtotal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    iva_rate: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    iva_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[BillingDocumentStatus] = mapped_column(
        SAEnum(BillingDocumentStatus, name="billing_document_status"),
        default=BillingDocumentStatus.draft,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    client = relationship("BillingClient", backref="documents")
    items: Mapped[list["BillingDocumentItem"]] = relationship(
        "BillingDocumentItem", back_populates="document",
        cascade="all, delete-orphan",
    )


class BillingDocumentItem(UUIDMixin, Base):
    __tablename__ = "billing_document_items"

    document_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_documents.id"), nullable=False, index=True
    )
    product_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_products.id"), nullable=True
    )

    description: Mapped[str] = mapped_column(String(512), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    discount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    has_iva: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    line_total: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    # Relationships
    document = relationship("BillingDocument", back_populates="items")
    product = relationship("BillingProduct", backref="document_items")
