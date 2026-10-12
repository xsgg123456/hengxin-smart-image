from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, Integer, String, Text, JSON, UniqueConstraint, CheckConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps
from app.overseas.db import Base


class Picture(Timestamps, Base):
    __tablename__ = 'overseas_pictures'
    __table_args__ = (UniqueConstraint('task_id', 'sku', 'position'), CheckConstraint('version >= 0'))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_plans.id'))
    job_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_jobs.id'))
    sku: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    version: Mapped[int] = mapped_column(Integer, default=0)
    approved_version: Mapped[int | None] = mapped_column(Integer)


class PictureVersion(Timestamps, Base):
    __tablename__ = 'overseas_picture_versions'
    __table_args__ = (UniqueConstraint('picture_id', 'version'), CheckConstraint('version >= 1'))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    picture_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_pictures.id'), index=True)
    job_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_jobs.id'))
    version: Mapped[int] = mapped_column(Integer)
    bucket: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default='')
    marks: Mapped[list] = mapped_column(JSON, default=list)
