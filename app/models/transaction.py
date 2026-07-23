"""Transaction and Budget models — personal finance tracking.

Design rules:
- All datetimes in local Ecuador time (no TZ conversions — AGENTS.md §2.4).
- amount is always positive; type (expense/income) defines the sign.
- Categories are predefined ENUMs for deterministic queries.
- One active budget per user+category (unique constraint).
"""

import uuid as _uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, Integer, Numeric, DateTime, Boolean, ForeignKey, Enum as SAEnum, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID as SA_UUID

from app.models.base import UUIDMixin, TimestampMixin, Base


# ---- ENUMs ----

class TransactionType(str, Enum):
    expense = "expense"
    income = "income"


class TransactionCategory(str, Enum):
    # Expense categories
    food = "food"
    transport = "transport"
    housing = "housing"
    health = "health"
    entertainment = "entertainment"
    services = "services"
    education = "education"
    clothing = "clothing"
    other_expense = "other_expense"
    # Income categories
    salary = "salary"
    business = "business"
    gift = "gift"
    investment = "investment"
    other_income = "other_income"


class BudgetPeriod(str, Enum):
    monthly = "monthly"
    weekly = "weekly"


# ---- Models ----

class Transaction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "transactions"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, name="transaction_type"), nullable=False
    )

    amount: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    category: Mapped[TransactionCategory] = mapped_column(
        SAEnum(TransactionCategory, name="transaction_category"), nullable=False
    )

    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=datetime.now, index=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    attributes: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    user = relationship("User", backref="transactions")

    __table_args__ = (
        Index("idx_transactions_user_date", "user_id", "transaction_date"),
    )


class Budget(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "budgets"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    category: Mapped[TransactionCategory] = mapped_column(
        SAEnum(TransactionCategory, name="transaction_category"), nullable=False
    )

    amount: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    period: Mapped[BudgetPeriod] = mapped_column(
        SAEnum(BudgetPeriod, name="budget_period"), default=BudgetPeriod.monthly, nullable=False
    )

    alert_threshold: Mapped[int] = mapped_column(
        Integer, default=80, nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    attributes: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    user = relationship("User", backref="budgets")

    __table_args__ = (
        Index("idx_budgets_user_category", "user_id", "category", unique=True, postgresql_where=(is_active is True)),
    )
