from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps
from app.overseas.db import Base


class Material(Timestamps, Base):
    __tablename__ = 'overseas_materials'
    __table_args__ = (UniqueConstraint('task_id', 'kind'),
                     CheckConstraint("kind IN ('requirement', 'competitor')"),
                     CheckConstraint('version >= 0'))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'), index=True)
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(255))
    bucket: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(200), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    checksum: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='staging')
    version: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ParseVersion(Timestamps, Base):
    __tablename__ = 'overseas_material_versions'
    __table_args__ = (UniqueConstraint('material_id', 'version'), CheckConstraint('version >= 1'))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    material_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_materials.id'), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    parser_version: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(Text, default='')
    error: Mapped[str | None] = mapped_column(String(500))
