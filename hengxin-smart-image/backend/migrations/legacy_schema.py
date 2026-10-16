"""Frozen historic schema for revisions 0005-0007; never runtime metadata."""
from sqlalchemy import Table, Column, Uuid
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

for name in ('users', 'files', 'skill_versions', 'job_records'):
    Table(name, Base.metadata, Column('id', Uuid, primary_key=True))

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.timestamps import Timestamps

ACTIVE = ('queued', 'running', 'collecting', 'cancelling', 'uncertain')


class TaskRecord(Timestamps, Base):
    __tablename__ = 'task_records'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(200))
    sku: Mapped[str] = mapped_column(String(200), default='')
    mode: Mapped[str] = mapped_column(String(20))
    template_snapshot: Mapped[dict | None] = mapped_column(JSON)
    skill_version_id: Mapped[UUID | None] = mapped_column(ForeignKey('skill_versions.id'))
    skill_snapshot: Mapped[dict] = mapped_column(JSON)
    builtin_prompt: Mapped[dict | None] = mapped_column(JSON)
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
    base_version_id: Mapped[UUID | None] = mapped_column(ForeignKey(
        'image_versions.id', name='fk_execution_rounds_base_version_id', use_alter=True))
    annotation_file_id: Mapped[UUID | None] = mapped_column(ForeignKey(
        'files.id', name='fk_execution_rounds_annotation_file_id'))
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

"""Durable CLI identities and observations; publication still requires PG claims."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import utcnow
from app.db.timestamps import Timestamps


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
    # One logical attempt per round; bounded internal continuation keeps separate logs.
    # Redelivery and recovery never create another invocation.
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
    observation: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)


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

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.timestamps import Timestamps


class ArchiveRecord(Timestamps, Base):
    __tablename__ = 'archives'
    __table_args__ = (Index('uq_archive_live_snapshot', 'task_id', 'snapshot_hash', unique=True,
        postgresql_where=text('deleted_at IS NULL'), sqlite_where=text('deleted_at IS NULL')),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('task_records.id'), index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(20))
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArchiveImage(Timestamps, Base):
    __tablename__ = 'archive_images'
    __table_args__ = (UniqueConstraint('archive_id', 'slot'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    archive_id: Mapped[UUID] = mapped_column(ForeignKey('archives.id'), index=True)
    slot: Mapped[int] = mapped_column(Integer)
    image_version_id: Mapped[UUID] = mapped_column(ForeignKey('image_versions.id'))
    file_id: Mapped[UUID] = mapped_column(ForeignKey('files.id'))


class ArchiveRequest(Timestamps, Base):
    __tablename__ = 'archive_requests'
    __table_args__ = (UniqueConstraint('task_id', 'user_id', 'key'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('task_records.id'))
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    key: Mapped[str] = mapped_column(String(128))
    body_hash: Mapped[str] = mapped_column(String(64))
    archive_id: Mapped[UUID] = mapped_column(ForeignKey('archives.id'))

"""Durable object deletion receipt; no foreign key to already collected metadata."""
from uuid import UUID, uuid4
from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps


class CleanupObject(Timestamps, Base):
    __tablename__ = 'cleanup_objects'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    bucket: Mapped[str] = mapped_column(String(63))
    object_key: Mapped[str] = mapped_column(String(200), unique=True)
