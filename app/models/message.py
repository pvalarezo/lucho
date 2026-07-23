"""Message model — raw log of every incoming message (text / audio / photo)."""

import uuid as _uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, Base, now_ec

import enum


class MessageChannel(str, enum.Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"


class MessageType(str, enum.Enum):
    text = "text"
    audio = "audio"
    photo = "photo"


class MessageStatus(str, enum.Enum):
    received = "received"
    acked = "acked"              # "Recibido, dame un segundo" sent
    extracted = "extracted"      # LLM extraction done
    confirmed = "confirmed"      # user confirmed or corrected
    persisted = "persisted"      # data written to target tables
    error = "error"


class Message(UUIDMixin, Base):
    __tablename__ = "messages"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    channel: Mapped[MessageChannel] = mapped_column(
        Enum(MessageChannel, name="message_channel"), nullable=False
    )
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type"), nullable=False
    )

    # Raw content
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )  # MinIO object key for audio / photo
    transcription: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Whisper output

    # Extraction result (LLM output as JSON)
    extraction_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Status tracking
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, name="message_status"),
        default=MessageStatus.received,
        nullable=False,
    )

    # Timestamps per stage (for latency / debugging)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=now_ec, nullable=False
    )
    acked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    persisted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # Relationship
    user = relationship("User", backref="messages")
