"""Pydantic schemas for Message request/response."""

import uuid
from datetime import datetime
from pydantic import BaseModel

from app.models.message import MessageChannel, MessageType, MessageStatus


class MessageRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel: MessageChannel
    message_type: MessageType
    text: str | None
    file_path: str | None
    transcription: str | None
    extraction_result: dict | None
    status: MessageStatus
    received_at: datetime
    acked_at: datetime | None
    extracted_at: datetime | None
    confirmed_at: datetime | None
    persisted_at: datetime | None

    model_config = {"from_attributes": True}
