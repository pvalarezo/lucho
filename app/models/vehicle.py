"""Vehicle and VehicleMaintenance models — dedicated vehicle management.

Replaces the previous asset-based vehicle storage (AssetType.vehicle).
Maximum 2 vehicles per user enforced at the application layer.
"""

import uuid as _uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import String, Integer, Float, Date, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, TimestampMixin, Base


class Vehicle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # ---- Core identity ----
    plate: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )  # uppercase, no dashes (e.g., "PBC1234")

    brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ---- Technical identifiers ----
    engine_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chassis_number: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ---- Computed by vehicle_rules.py ----
    last_digit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pico_y_placa_days: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # e.g., "Lunes" or "Lunes y Viernes"
    next_matriculation: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ---- Expiry dates ----
    soat_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    rtv_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ---- Notes ----
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Soft delete ----
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Relationships ----
    maintenances: Mapped[list["VehicleMaintenance"]] = relationship(
        "VehicleMaintenance", back_populates="vehicle", lazy="selectin",
        order_by="VehicleMaintenance.performed_at.desc()",
    )


class MaintenanceType(str, Enum):
    oil_change = "oil_change"
    brakes = "brakes"
    tires = "tires"
    battery = "battery"
    general = "general"
    other = "other"


class VehicleMaintenance(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "vehicle_maintenances"

    vehicle_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False, index=True
    )

    maintenance_type: Mapped[MaintenanceType] = mapped_column(
        SAEnum(
            MaintenanceType,
            name="maintenance_type",
            create_type=True,
        ),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    mileage_km: Mapped[int | None] = mapped_column(Integer, nullable=True)

    performed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    next_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_mileage_km: Mapped[int | None] = mapped_column(Integer, nullable=True)

    receipt_file_key: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )  # factura/comprobante en MinIO

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Relationship ----
    vehicle: Mapped["Vehicle"] = relationship(
        "Vehicle", back_populates="maintenances"
    )
