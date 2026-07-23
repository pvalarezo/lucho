"""Pydantic schemas for Asset — with discriminator by asset_type."""

import uuid
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field

from app.models.asset import AssetType


# ---- Per-type attribute schemas ----

class VehicleAttributes(BaseModel):
    """Attributes for asset_type = vehicle."""
    plate: str | None = None
    last_digit: int | None = None       # for matriculación
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    soat_expiry: str | None = None      # ISO date
    rtv_expiry: str | None = None


class CreditCardAttributes(BaseModel):
    """Attributes for asset_type = credit_card."""
    bank: str | None = None
    last_four_digits: str | None = None
    cut_off_day: int | None = None      # day of month
    payment_due_day: int | None = None


class WarrantyAttributes(BaseModel):
    """Attributes for asset_type = warranty."""
    product: str | None = None
    store: str | None = None
    purchase_date: str | None = None
    warranty_months: int | None = None
    invoice_photo: str | None = None    # MinIO object key


class SubscriptionAttributes(BaseModel):
    """Attributes for asset_type = subscription."""
    service_name: str | None = None
    billing_cycle: str | None = None    # monthly, yearly
    next_payment: str | None = None
    amount: float | None = None


class DocumentAttributes(BaseModel):
    """Attributes for asset_type = document (cédula, pasaporte, licencia)."""
    document_type: str | None = None    # cedula, pasaporte, licencia
    document_number: str | None = None
    expiry_date: str | None = None
    issuing_country: str = "EC"


class InsuranceAttributes(BaseModel):
    """Attributes for asset_type = insurance (SOAT, etc.)."""
    policy_number: str | None = None
    provider: str | None = None
    expiry_date: str | None = None
    coverage_type: str | None = None


class OtherAttributes(BaseModel):
    """Catch-all for asset_type = other or future types."""
    pass


# ---- Discriminated union for attribute validation ----

AssetAttributes = Annotated[
    VehicleAttributes
    | CreditCardAttributes
    | WarrantyAttributes
    | SubscriptionAttributes
    | DocumentAttributes
    | InsuranceAttributes
    | OtherAttributes
    | dict,
    Field(discriminator="asset_type"),
]


# ---- Request / Response schemas ----

class AssetCreate(BaseModel):
    asset_type: AssetType
    name: str
    attributes: dict = {}
    notes: str | None = None


class AssetUpdate(BaseModel):
    name: str | None = None
    attributes: dict | None = None
    notes: str | None = None


class AssetRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    asset_type: AssetType
    name: str
    attributes: dict
    attributes_schema_version: int
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
