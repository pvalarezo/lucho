"""Project and ProjectTask models — self-contained task grouping.

Design rules (spec section 9.6):
- Simple: no dependencies between tasks, no formal project management
- Tasks have status (pending/done) and optional due_date
- Single reminder on due_date (no escalated windows like events)
- Projects can be archived
"""

import uuid as _uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import String, Text, Date, DateTime, Boolean, ForeignKey, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UUID

from app.models.base import UUIDMixin, TimestampMixin, Base, utcnow


class ProjectStatus(str, Enum):
    active = "active"
    archived = "archived"


class TaskStatus(str, Enum):
    pending = "pending"
    done = "done"


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)

    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, name="project_status"),
        default=ProjectStatus.active,
        nullable=False,
    )

    __table_args__ = (
        Index("idx_projects_user_name", "user_id", "name", unique=True),
    )


class ProjectTask(UUIDMixin, Base):
    __tablename__ = "project_tasks"

    project_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status"),
        default=TaskStatus.pending,
        nullable=False,
    )

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_project_tasks_project_status", "project_id", "status"),
        Index("idx_project_tasks_due_date", "due_date"),
    )
