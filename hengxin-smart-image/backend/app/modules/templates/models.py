from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.resource_models import Timestamps


class TemplateRecord(Timestamps, Base):
    __tablename__ = 'templates'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    version: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TemplateVersionRecord(Timestamps, Base):
    __tablename__ = 'template_versions'
    __table_args__ = (
        UniqueConstraint('template_id', 'version'),
        CheckConstraint("mode IN ('wallpaper','product')"),
        CheckConstraint("skill_binding IN ('module_default','specific')"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    template_id: Mapped[UUID] = mapped_column(ForeignKey('templates.id'))
    version: Mapped[int] = mapped_column(Integer)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    operator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean)
    skill_binding: Mapped[str] = mapped_column(String(20))
    skill_version_id: Mapped[UUID | None] = mapped_column(ForeignKey('skill_versions.id'))
    skill_name: Mapped[str] = mapped_column(String(200))


class TemplateImageRecord(Timestamps, Base):
    __tablename__ = 'template_images'
    __table_args__ = (UniqueConstraint('template_version_id', 'slot'), CheckConstraint('slot >= 0 AND slot < 20'))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    template_version_id: Mapped[UUID] = mapped_column(ForeignKey('template_versions.id'))
    file_id: Mapped[UUID] = mapped_column(ForeignKey('files.id'))
    slot: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
