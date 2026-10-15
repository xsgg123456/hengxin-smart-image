"""Minimal durable deletion receipt, deliberately independent of business rows."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.resource_models import Timestamps


class ApiTaskDeletion(Timestamps, Base):
    __tablename__ = 'api_task_deletions'
    task_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(20), default='deleting', index=True)
    phase: Mapped[str] = mapped_column(String(20), default='requested')
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(200))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
