"""Pydantic schemas for List and ListItem."""

import uuid
from datetime import datetime
from pydantic import BaseModel

from app.models.list import ListType, ItemStatus


class ListCreate(BaseModel):
    name: str
    list_type: ListType = ListType.generic


class ListRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    list_type: ListType
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ListItemCreate(BaseModel):
    list_name: str = "general"
    items: list[str]
    quantity: str | None = None


class ListItemUpdate(BaseModel):
    content: str | None = None
    status: ItemStatus | None = None
    quantity: str | None = None


class ListItemRead(BaseModel):
    id: uuid.UUID
    list_id: uuid.UUID
    content: str
    status: ItemStatus
    quantity: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
