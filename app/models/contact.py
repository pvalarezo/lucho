"""Contact and CaregiverLink models — third parties and family care relationships."""

import uuid as _uuid

from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, TimestampMixin, Base


class Contact(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "contacts"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)

    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    telegram_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    whatsapp_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    relationship: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # "friend", "family", "colleague", "parent", etc.

    is_emergency_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    contact_notes: Mapped[str | None] = mapped_column(String(512), nullable=True)


class CaregiverLink(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "caregiver_links"

    caregiver_user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    cared_for_user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    cared_for_contact_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
