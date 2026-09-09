from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.resource_models import Timestamps

ACTIVE = ('queued', 'running', 'collecting', 'cancelling', 'uncertain')


class TaskRecord(Timestamps, Base):
    __tablename__ = 'task_records'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(200))
    sku: Mapped[str] = mapped_column(String(200), default='')
    mode: Mapped[str] = mapped_column(String(20))
    template_snapshot: Mapped[dict | None] = mapped_column(JSON)
    skill_version_id: Mapped[UUID] = mapped_column(ForeignKey('skill_versions.id'))
    skill_snapshot: Mapped[dict] = mapped_column(JSON)
    current_round_id: Mapped[UUID | None] = mapped_column(Uuid)
    execution_source: Mapped[str] = mapped_column(String(20), default='fixture')
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoundRecord(Timestamps, Base):
    __tablename__ = 'execution_rounds'
    __table_args__ = (Index('uq_task_active_round', 'task_id', unique=True,
        postgresql_where=text("status IN ('queued','running','collecting','cancelling','uncertain')"),
        sqlite_where=text("status IN ('queued','running','collecting','cancelling','uncertain')")),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('task_records.id'), index=True)
    job_id: Mapped[UUID] = mapped_column(ForeignKey('job_records.id'), unique=True)
    operator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    target: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_config: Mapped[dict] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class TaskRequest(Timestamps, Base):
    __tablename__ = 'task_requests'
    __table_args__ = (UniqueConstraint('user_id', 'operation', 'target', 'key'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    operation: Mapped[str] = mapped_column(String(30))
    target: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(128))
    body_hash: Mapped[str] = mapped_column(String(64))
    task_id: Mapped[UUID] = mapped_column(ForeignKey('task_records.id'))
    round_id: Mapped[UUID] = mapped_column(ForeignKey('execution_rounds.id'))


class TaskSource(Timestamps, Base):
    __tablename__ = 'task_sources'
    __table_args__ = (UniqueConstraint('task_id', 'slot'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('task_records.id'))
    slot: Mapped[int] = mapped_column(Integer)
    file_id: Mapped[UUID] = mapped_column(ForeignKey('files.id'))
    name: Mapped[str] = mapped_column(String(200))


class ResultSlotRecord(Timestamps, Base):
    __tablename__ = 'result_slots'
    __table_args__ = (UniqueConstraint('task_id', 'slot'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('task_records.id'))
    slot: Mapped[int] = mapped_column(Integer)
    current_version_id: Mapped[UUID | None] = mapped_column(Uuid)
    error: Mapped[str | None] = mapped_column(Text)


class ImageVersion(Timestamps, Base):
    __tablename__ = 'image_versions'
    __table_args__ = (UniqueConstraint('slot_id', 'version'), UniqueConstraint('slot_id', 'round_id'))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    slot_id: Mapped[UUID] = mapped_column(ForeignKey('result_slots.id'))
    round_id: Mapped[UUID] = mapped_column(ForeignKey('execution_rounds.id'))
    version: Mapped[int] = mapped_column(Integer)
    file_id: Mapped[UUID] = mapped_column(ForeignKey('files.id'))


class ExecutionGate(Timestamps, Base):
    __tablename__ = 'execution_gate'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
