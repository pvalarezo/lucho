"""Topic and Note models — free-form content grouped by user-defined topics.

Design rules (spec section 9.2):
- topics: user-defined grouping name, one per user
- notes: free text content under a topic, with pgvector embedding for semantic search
- No fixed field structure — just content TEXT
"""

import uuid as _uuid

from sqlalchemy import String, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID
from pgvector.sqlalchemy import Vector

from app.models.base import UUIDMixin, TimestampMixin, Base


class Topic(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "topics"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)

    # Relationship
    user = relationship("User", backref="topics")
    notes = relationship("Note", back_populates="topic", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_topics_user_name", "user_id", "name", unique=True),
    )


class Note(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notes"

    topic_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id"), nullable=False, index=True
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Embedding for semantic search (populated on write)
    embedding = mapped_column(Vector(1024), nullable=True)

    # Link back to the source message (optional, for traceability)
    source_message_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )

    # Relationship
    topic = relationship("Topic", back_populates="notes")
    source_message = relationship("Message", backref="notes")

    __table_args__ = (
        Index("idx_notes_embedding", "embedding", postgresql_using="hnsw"),
    )
