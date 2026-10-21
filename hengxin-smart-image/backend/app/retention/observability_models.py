"""Independent receipts intentionally have no foreign keys to business records."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.resource_models import Timestamps


class RetentionRecord(Timestamps, Base):
    __tablename__ = 'cli_retention_records'
    __table_args__ = (UniqueConstraint('resource_id', 'kind', 'last_activity_at'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    resource_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    task_id: Mapped[UUID | None] = mapped_column(Uuid)
    task_name: Mapped[str] = mapped_column(String(60))
    image_position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    result: Mapped[str] = mapped_column(String(30), index=True)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    turns_removed: Mapped[int] = mapped_column(Integer, default=0)
    objects_removed: Mapped[int] = mapped_column(Integer, default=0)
    objects_pending: Mapped[int] = mapped_column(Integer, default=0)
    counted: Mapped[bool] = mapped_column(Boolean, default=False)


class RetentionObjectLink(Timestamps, Base):
    __tablename__ = 'cli_retention_object_links'
    __table_args__ = (UniqueConstraint('record_id', 'object_id'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    record_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    object_id: Mapped[UUID] = mapped_column(Uuid, index=True)


class RetentionRun(Timestamps, Base):
    __tablename__ = 'cli_retention_runs'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20))


class RetentionService(Timestamps, Base):
    __tablename__ = 'cli_retention_service'
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RetentionTotals(Timestamps, Base):
    __tablename__ = 'cli_retention_totals'
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cache_total: Mapped[int] = mapped_column(Integer, default=0)
    history_total: Mapped[int] = mapped_column(Integer, default=0)
