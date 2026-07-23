"""List and ListItem models — shopping lists, task lists with pending/done status.

Design rules (spec section 9.3):
- lists: named container with list_type discriminator
- list_items: individual items with status (pending/done) and optional quantity
- Status transitions are deterministic, not LLM-driven
"""

import uuid as _uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID
from pgvector.sqlalchemy import Vector

from app.models.base import UUIDMixin, TimestampMixin, Base, now_ec


class ListType(str, Enum):
    shopping = "shopping"
    tasks = "tasks"
    generic = "generic"


class ItemStatus(str, Enum):
    pending = "pending"
    done = "done"


class List(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "lists"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)

    list_type: Mapped[ListType] = mapped_column(
        SAEnum(ListType, name="list_type"),
        default=ListType.generic,
        nullable=False,
    )

    # Relationship
    user = relationship("User", backref="lists")
    items = relationship("ListItem", back_populates="list", cascade="all, delete-orphan")


class ListItem(UUIDMixin, Base):
    __tablename__ = "list_items"

    list_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lists.id"), nullable=False, index=True
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[ItemStatus] = mapped_column(
        SAEnum(ItemStatus, name="item_status"),
        default=ItemStatus.pending,
        nullable=False,
    )

    quantity: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=now_ec, nullable=False
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # Embedding for semantic search
    embedding = mapped_column(Vector(1024), nullable=True)

    # Relationship
    list = relationship("List", back_populates="items")

    __table_args__ = (
        Index("idx_list_items_list_status", "list_id", "status"),
    )
