"""Pydantic schemas for Topic and Note."""

import uuid
from datetime import datetime
from pydantic import BaseModel


class TopicCreate(BaseModel):
    name: str


class TopicRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NoteCreate(BaseModel):
    topic_name: str  # resolves or creates topic
    content: str
    source_message_id: uuid.UUID | None = None


class NoteRead(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    content: str
    source_message_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
