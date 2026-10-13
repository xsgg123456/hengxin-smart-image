"""Overseas execution records never share domestic business metadata."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps, utcnow
from app.overseas.db import Base
from app.overseas.auth import models as member_models  # noqa: F401 - standalone worker metadata
from app.overseas.tasks import models as task_models  # noqa: F401

KINDS = ('analysis', 'reanalysis', 'generation', 'revision', 'studio')
ACTIVE = ('running', 'collecting', 'cancelling', 'uncertain')
TERMINAL = ('succeeded', 'failed', 'cancelled')


class ExecutionGate(Timestamps, Base):
    __tablename__ = 'overseas_execution_gate'
    __table_args__ = (CheckConstraint('id = 1'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)


class Job(Timestamps, Base):
    __tablename__ = 'overseas_jobs'
    __table_args__ = (CheckConstraint('version >= 1'),
        CheckConstraint("kind IN ('analysis','reanalysis','generation','revision','studio')"),
        CheckConstraint("status IN ('queued','running','collecting','cancelling','uncertain','succeeded','failed','cancelled')"))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    claim_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_node: Mapped[str | None] = mapped_column(String(200))
    process_id: Mapped[int | None] = mapped_column(Integer)
    process_boot: Mapped[str | None] = mapped_column(String(200))
    process_started: Mapped[str | None] = mapped_column(String(200))
    process_exited: Mapped[bool] = mapped_column(Boolean, default=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_count: Mapped[int] = mapped_column(Integer, default=0)
    usage: Mapped[dict | None] = mapped_column(JSON)


class JobOutbox(Timestamps, Base):
    __tablename__ = 'overseas_job_outbox'
    job_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_jobs.id'), primary_key=True)
    dispatch_count: Mapped[int] = mapped_column(Integer, default=0)
    next_dispatch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExecutionEvent(Timestamps, Base):
    __tablename__ = 'overseas_execution_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    job_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_jobs.id'), index=True)
    status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(100))
