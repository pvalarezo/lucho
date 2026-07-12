"""SharedExpense and Participant models — group expenses, split bills, tandas.

Design rules (spec section 9.5):
- shared_expenses: one expense split among multiple people
- shared_expense_participants: each person's share, paid status
- Supports: equal split and custom amounts
"""

import uuid as _uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import String, Text, Float, Date, DateTime, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, TimestampMixin, Base, utcnow


class SplitType(str, Enum):
    equal = "equal"
    custom = "custom"


class ParticipantStatus(str, Enum):
    pending = "pending"
    paid = "paid"


class SharedExpense(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "shared_expenses"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    description: Mapped[str] = mapped_column(String(512), nullable=False)

    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    split_type: Mapped[SplitType] = mapped_column(
        SAEnum(SplitType, name="split_type"),
        default=SplitType.equal,
        nullable=False,
    )

    expense_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = ()


class SharedExpenseParticipant(UUIDMixin, Base):
    __tablename__ = "shared_expense_participants"

    expense_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_expenses.id"), nullable=False, index=True
    )

    contact_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)

    amount: Mapped[float] = mapped_column(Float, nullable=False)

    status: Mapped[ParticipantStatus] = mapped_column(
        SAEnum(ParticipantStatus, name="participant_status"),
        default=ParticipantStatus.pending,
        nullable=False,
    )

    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
