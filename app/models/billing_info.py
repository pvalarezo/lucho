"""BillingInfo model — tax invoice recipient data for SRI (Ecuador).

A user can have multiple billing profiles:
  - "personal" — their own cédula
  - "empresa" — company RUC
  - "tercero" — billing on behalf of someone else

One profile is marked as default. When a subscription invoice is issued,
the default billing info is copied into the invoice record (immutable snapshot).
"""

import uuid as _uuid

from sqlalchemy import String, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, TimestampMixin, Base


class BillingInfo(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "billing_info"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # ---- Label to identify this profile ----
    label: Mapped[str] = mapped_column(
        String(64), nullable=False, default="personal"
    )  # "personal", "empresa", "mi papá"

    # ---- Billing recipient ----
    full_name: Mapped[str] = mapped_column(
        String(256), nullable=False
    )  # Nombre completo o Razón Social

    id_number: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # Cédula (10 dígitos) o RUC (13 dígitos)

    id_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="cedula"
    )  # "cedula", "ruc", "pasaporte", "consumidor_final"

    email: Mapped[str] = mapped_column(
        String(256), nullable=False
    )  # Required by SRI for electronic invoicing

    phone: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )

    address: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )  # Required by SRI: "Av. Amazonas N24-33 y Colón, Quito"

    # ---- Flags ----
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Relationship
    user = relationship("User", backref="billing_profiles")

    __table_args__ = (
        Index("idx_billing_info_user_default", "user_id", "is_default"),
    )
