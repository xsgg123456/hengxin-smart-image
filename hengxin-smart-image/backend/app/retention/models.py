from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, Integer, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.resource_models import Timestamps


class RetentionEntry(Timestamps, Base):
    __tablename__ = 'cli_retention'
    __table_args__ = (UniqueConstraint('domain', 'resource_id'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    domain: Mapped[str] = mapped_column(String(20))
    resource_id: Mapped[UUID] = mapped_column(Uuid)
    initialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_cleanup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    cache_cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default='active')
    error: Mapped[str | None] = mapped_column(String(200))
    counters: Mapped[dict] = mapped_column(JSON, default=dict)


class RetentionObject(Timestamps, Base):
    __tablename__ = 'cli_retention_objects'
    __table_args__ = (UniqueConstraint('bucket', 'object_key'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    bucket: Mapped[str] = mapped_column(String(63))
    object_key: Mapped[str] = mapped_column(String(200))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

