"""Asset model — what the user owns or tracks (vehicle, credit card, warranty, etc.).

Design rules from spec:
- asset_type + name + attributes (JSONB with schema version)
- GIN index on attributes for flexible search
- Soft delete via deleted_at
- Never store binaries — only MinIO references inside attributes
"""

import uuid as _uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, TimestampMixin, Base, utcnow

import enum


class AssetType(str, enum.Enum):
    """Closed enum for asset_type — validated by PostgreSQL ENUM."""

    vehicle = "vehicle"
    credit_card = "credit_card"
    warranty = "warranty"
    subscription = "subscription"
    document = "document"           # cédula, pasaporte, licencia
    insurance = "insurance"         # SOAT, pólizas
    tax = "tax"                     # RUC, deducibles
    property = "property"           # bienes raíces
    pet = "pet"
    other = "other"


class Asset(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "assets"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="asset_type"), nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(256), nullable=False
    )

    # Flexible attributes per vertical (schema validated in Pydantic, not DB)
    attributes: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # Schema version for attributes — safety hatch for data migrations
    attributes_schema_version: Mapped[int] = mapped_column(
        default=1, nullable=False
    )

    # Embedding for semantic search (populated on write)
    embedding: Mapped[list[float] | None] = mapped_column(
        nullable=True
    )  # pgvector VECTOR type set via Alembic migration

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Optional note for context
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    user = relationship("User", backref="assets")

    __table_args__ = (
        Index("idx_assets_attributes", "attributes", postgresql_using="gin"),
    )
