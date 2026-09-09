from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.resource_models import Timestamps


class SkillRecord(Timestamps, Base):
    __tablename__ = 'skills'
    __table_args__ = (UniqueConstraint('name', 'mode'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)


class SkillVersionRecord(Timestamps, Base):
    __tablename__ = 'skill_versions'
    __table_args__ = (UniqueConstraint('skill_id', 'version'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    skill_id: Mapped[UUID] = mapped_column(ForeignKey('skills.id'))
    skill: Mapped[SkillRecord] = relationship(lazy='joined')
    version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default='uploaded')
    checksum: Mapped[str] = mapped_column(String(64))
    bucket: Mapped[str] = mapped_column(String(63))
    object_key: Mapped[str] = mapped_column(String(200), unique=True)
    content_type: Mapped[str] = mapped_column(String(50), default='application/zip')
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    node: Mapped[str | None] = mapped_column(String(200))
    error: Mapped[str | None] = mapped_column(Text)
    installed_path: Mapped[str | None] = mapped_column(Text)
    current_job_id: Mapped[UUID | None] = mapped_column(Uuid)


class ModuleSkillBinding(Timestamps, Base):
    __tablename__ = 'module_skill_bindings'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    mode: Mapped[str] = mapped_column(String(20), unique=True)
    skill_version_id: Mapped[UUID | None] = mapped_column(ForeignKey('skill_versions.id'))
    operator_id: Mapped[UUID | None] = mapped_column(ForeignKey('users.id'))


class SkillAuditRecord(Timestamps, Base):
    __tablename__ = 'skill_audits'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    operator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(Text)
