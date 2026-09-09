"""Stable identities and private resource metadata; development identities stay distinct."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, utcnow


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserRecord(Timestamps, Base):
    __tablename__ = 'users'
    __table_args__ = (
        CheckConstraint("status IN ('active','pending','disabled')"),
        CheckConstraint("role IN ('super_admin','design_manager','designer','operator')"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    identity_source: Mapped[str] = mapped_column(String(20))


class FileRecord(Timestamps, Base):
    __tablename__ = 'files'
    __table_args__ = (CheckConstraint("status IN ('staging','ready','failed')"),)
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


class DeletionRecord(Timestamps, Base):
    __tablename__ = 'deletion_records'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    resource_type: Mapped[str] = mapped_column(String(30))
    resource_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    operator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
