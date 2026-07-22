"""BusinessInfo model — company-level configuration for payments and invoicing.

Stores AURACORE's business data used in payment instructions and SRI invoicing.
Single-row table: only one active record at a time.
"""

from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDMixin, TimestampMixin, Base


class BusinessInfo(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "business_info"

    # ---- Company identity ----
    company_name: Mapped[str] = mapped_column(
        String(256), nullable=False, default="AURACORE SOLUCIONES SAS"
    )
    ruc: Mapped[str] = mapped_column(
        String(13), nullable=False, default="1790012345001"
    )
    legal_representative: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )

    # ---- Bank info for transfers ----
    bank_name: Mapped[str] = mapped_column(
        String(128), nullable=False, default="Banco Pichincha"
    )
    account_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="corriente"
    )
    account_number: Mapped[str] = mapped_column(
        String(32), nullable=False, default="2201234567"
    )

    # ---- Contact ----
    support_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    support_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ---- Active flag (only one row active at a time) ----
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
