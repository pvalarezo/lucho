"""User model — core identity for every Lucho account."""

from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDMixin, TimestampMixin, Base


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    telegram_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    whatsapp_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(
        String(32), unique=True, nullable=True
    )
    language: Mapped[str] = mapped_column(
        String(8), default="es", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    preferred_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    onboarding_complete: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    onboarding_step: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # 0=not started, 1=awaiting name, 2=done

    # Relationships
    profile: Mapped["UserProfile | None"] = relationship(  # noqa: F821
        "UserProfile", back_populates="user", uselist=False, lazy="selectin"
    )
    subscription: Mapped["Subscription | None"] = relationship(  # noqa: F821
        "Subscription", back_populates="user", uselist=False, lazy="selectin"
    )
