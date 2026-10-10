"""Minimal durable business facts: deliberately no foreign keys to retained sources."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.resource_models import Timestamps


class ApiUsageFact(Timestamps, Base):
    __tablename__ = 'api_usage_facts'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(160), unique=True)
    category: Mapped[str] = mapped_column(String(30), index=True)
    channel: Mapped[str] = mapped_column(String(12))
    kind: Mapped[str] = mapped_column(String(30))
    task_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    task_name: Mapped[str] = mapped_column(String(60))
    owner_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    operator_id: Mapped[UUID | None] = mapped_column(Uuid)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    is_retry: Mapped[bool | None] = mapped_column(Boolean)
    attribution: Mapped[str] = mapped_column(String(30))
