"""Pydantic schemas for User request/response validation."""

import uuid
from datetime import datetime
from pydantic import BaseModel


class UserBase(BaseModel):
    first_name: str
    last_name: str | None = None
    language: str = "es"


class UserCreate(UserBase):
    telegram_id: str | None = None
    whatsapp_id: str | None = None
    phone_number: str | None = None


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
    language: str | None = None
    is_active: bool | None = None


class UserRead(UserBase):
    id: uuid.UUID
    telegram_id: str | None
    whatsapp_id: str | None
    phone_number: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
