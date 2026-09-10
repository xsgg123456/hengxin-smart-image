from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.resource_models import Timestamps


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
