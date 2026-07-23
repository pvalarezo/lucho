"""Document model — dedicated table for personal documents.

Replaces the generic assets table for document-type records.
Documents: cédula, pasaporte, licencia, SOAT, facturas, garantías,
pólizas de seguro, certificados, contratos, y cualquier documento
con fecha de vencimiento opcional.

Design rules:
- All dates in local Ecuador time (AGENTS.md §2.4).
- Soft delete via deleted_at.
- pgvector embedding for semantic search.
- Multiple file_keys supported via JSONB array.
"""

import uuid as _uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, Date, DateTime, ForeignKey, Enum as SAEnum, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID
from pgvector.sqlalchemy import Vector

from app.models.base import UUIDMixin, TimestampMixin, Base


class DocumentType(str, Enum):
    cedula = "cedula"
    pasaporte = "pasaporte"
    licencia = "licencia"
    soat = "soat"
    seguro = "seguro"
    factura = "factura"
    garantia = "garantia"
    certificado = "certificado"
    escritura = "escritura"
    contrato = "contrato"
    tarjeta = "tarjeta"
    otro = "otro"


class DocumentStatus(str, Enum):
    active = "active"
    expired = "expired"
    archived = "archived"


class Document(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)

    document_number: Mapped[str | None] = mapped_column(String(128), nullable=True)

    expiry_date: Mapped[datetime | None] = mapped_column(
        Date, nullable=True, index=True
    )

    entity_name: Mapped[str | None] = mapped_column(String(256), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    file_keys: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status"),
        default=DocumentStatus.active,
        nullable=False,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # Embedding for semantic search (pgvector)
    embedding = mapped_column(Vector(1024), nullable=True)

    user = relationship("User", backref="documents")

    __table_args__ = (
        Index("idx_documents_user_id", "user_id"),
        Index("idx_documents_expiry_date", "expiry_date"),
        Index("idx_documents_document_type", "document_type"),
        Index("idx_documents_user_type", "user_id", "document_type"),
    )
