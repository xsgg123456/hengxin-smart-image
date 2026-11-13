"""Independent domestic archive metadata and private file copies."""
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.timestamps import Timestamps
from app.models import Base


class Archive(Timestamps, Base):
    __tablename__ = 'domestic_studio_archives'
    __table_args__ = (CheckConstraint("workspace IN ('camera','case')"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), index=True)
    workspace: Mapped[str] = mapped_column(String(20), index=True)
    source_conversation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_conversation_name: Mapped[str] = mapped_column(String(30))
    product_name: Mapped[str] = mapped_column(String(60), index=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='preparing', server_default='preparing')
    error: Mapped[str | None] = mapped_column(Text)


class ArchiveFile(Timestamps, Base):
    __tablename__ = 'domestic_studio_archive_files'
    __table_args__ = (UniqueConstraint('archive_id', 'kind', 'source_id'),
                      CheckConstraint("kind IN ('upload','picture','output')"))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    archive_id: Mapped[UUID] = mapped_column(ForeignKey('domestic_studio_archives.id'), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[UUID] = mapped_column(Uuid)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    bucket: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    source_bucket: Mapped[str] = mapped_column(String(200))
    source_object_key: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default='pending', server_default='pending')
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)


class ArchiveRequest(Timestamps, Base):
    __tablename__ = 'domestic_studio_archive_requests'
    __table_args__ = (UniqueConstraint('user_id', 'operation', 'target', 'key'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    operation: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(80))
    key: Mapped[str] = mapped_column(String(128))
    body_hash: Mapped[str] = mapped_column(String(64))
    archive_id: Mapped[UUID] = mapped_column(Uuid)


class ArchiveDeletion(Timestamps, Base):
    __tablename__ = 'domestic_studio_archive_deletions'
    archive_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default='deleting', index=True)
    error: Mapped[str | None] = mapped_column(Text)
