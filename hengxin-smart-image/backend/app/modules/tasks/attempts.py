"""Durable CLI identities and observations; publication still requires PG claims."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, utcnow
from app.resource_models import Timestamps


class ExecutionSession(Timestamps, Base):
    __tablename__ = 'execution_sessions'
    task_id: Mapped[UUID] = mapped_column(ForeignKey('task_records.id'), primary_key=True)
    session_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(20), default='starting')


class ExecutionAttempt(Base):
    __tablename__ = 'execution_attempts'
    __table_args__ = (CheckConstraint(
        "status IN ('starting','running','finished','uncertain')",
        name='ck_execution_attempt_status'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    # No automatic retries: a redelivered round cannot create another invocation.
    round_id: Mapped[UUID] = mapped_column(ForeignKey('execution_rounds.id'), unique=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('task_records.id'), index=True)
    operator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    claim_token: Mapped[UUID] = mapped_column(Uuid)
    node: Mapped[str] = mapped_column(String(200))
    process_id: Mapped[int | None] = mapped_column(Integer)
    process_start: Mapped[str | None] = mapped_column(String(128))
    boot_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(20), default='starting')
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_code: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    workspace: Mapped[str] = mapped_column(Text)
    cli_version: Mapped[str] = mapped_column(String(64))


class ExecutionUsage(Base):
    __tablename__ = 'execution_usage'
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey('execution_attempts.id'), primary_key=True)
    data: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))


class WorkerHeartbeat(Base):
    __tablename__ = 'worker_heartbeats'
    node: Mapped[str] = mapped_column(String(200), primary_key=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    state: Mapped[str] = mapped_column(String(20), default='unknown')
    dependencies: Mapped[dict] = mapped_column(JSON, default=dict)
