from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, utcnow
from app.resource_models import Timestamps


class ApiFile(Timestamps, Base):
    __tablename__ = 'api_image_files'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(200))
    bucket: Mapped[str] = mapped_column(String(63))
    object_key: Mapped[str] = mapped_column(String(200), unique=True)
    content_type: Mapped[str] = mapped_column(String(50))
    checksum: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='staging')
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[UUID | None] = mapped_column(ForeignKey('users.id'))


class ApiTask(Timestamps, Base):
    __tablename__ = 'api_image_tasks'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    operator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(60))
    prompt: Mapped[str] = mapped_column(Text)
    material_id: Mapped[UUID] = mapped_column(ForeignKey('api_image_files.id'))
    parameters: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    error: Mapped[str | None] = mapped_column(String(300))
    events: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[UUID | None] = mapped_column(ForeignKey('users.id'))


class ApiItem(Timestamps, Base):
    __tablename__ = 'api_image_items'
    __table_args__ = (UniqueConstraint('task_id', 'position'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('api_image_tasks.id'), index=True)
    source_id: Mapped[UUID] = mapped_column(ForeignKey('api_image_files.id'))
    result_id: Mapped[UUID | None] = mapped_column(ForeignKey('api_image_files.id'))
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_version: Mapped[int | None] = mapped_column(Integer)
    revision_base_version: Mapped[int | None] = mapped_column(Integer)
    revision_source_id: Mapped[UUID | None] = mapped_column(ForeignKey('api_image_files.id'))
    revision_annotation_id: Mapped[UUID | None] = mapped_column(ForeignKey('api_image_files.id'))
    revision_text: Mapped[str | None] = mapped_column(Text)
    revision_snapshot: Mapped[dict | None] = mapped_column(JSON)
    revision_operator_id: Mapped[UUID | None] = mapped_column(ForeignKey('users.id'))
    position: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20), default='queued')
    retries: Mapped[int] = mapped_column(Integer, default=0)
    cycle_retries: Mapped[int] = mapped_column(Integer, default=0)
    collection_retries: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(300))
    # Private recovery data; serializers must never return upstream URLs or bytes.
    result_url: Mapped[str | None] = mapped_column(Text)
    result_bytes: Mapped[bytes | None] = mapped_column(LargeBinary)


class ApiAttempt(Timestamps, Base):
    __tablename__ = 'api_image_attempts'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(ForeignKey('api_image_items.id'), index=True)
    operator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    state: Mapped[str] = mapped_column(String(20), default='running')
    error: Mapped[str | None] = mapped_column(String(300))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey('users.id'))


class ApiDispatch(Timestamps, Base):
    __tablename__ = 'api_image_dispatch'
    id: Mapped[UUID] = mapped_column(ForeignKey('api_image_tasks.id'), primary_key=True)
    next_dispatch_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    dispatch_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiOperation(Timestamps, Base):
    __tablename__ = 'api_image_operations'
    __table_args__ = (UniqueConstraint('operator_id', 'key'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    operator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    key: Mapped[str] = mapped_column(String(128))
    payload_hash: Mapped[str] = mapped_column(String(64))
    task_id: Mapped[UUID] = mapped_column(ForeignKey('api_image_tasks.id'))


class ApiChannel(Timestamps, Base):
    __tablename__ = 'api_image_channel'
    __table_args__ = (CheckConstraint('id = 1'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(String(300))
    item_id: Mapped[UUID | None] = mapped_column(ForeignKey('api_image_items.id'))
    token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiVersion(Timestamps, Base):
    __tablename__ = 'api_image_versions'
    __table_args__ = (UniqueConstraint('item_id', 'number'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(ForeignKey('api_image_items.id'), index=True)
    number: Mapped[int] = mapped_column(Integer)
    file_id: Mapped[UUID] = mapped_column(ForeignKey('api_image_files.id'))
    operator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    text: Mapped[str] = mapped_column(Text, default='')
    annotation_id: Mapped[UUID | None] = mapped_column(ForeignKey('api_image_files.id'))
    base_version: Mapped[int | None] = mapped_column(Integer)
