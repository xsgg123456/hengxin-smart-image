from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, JSON, Uuid, String, Integer, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps
from app.overseas.db import Base


class Archive(Timestamps, Base):
    __tablename__ = 'overseas_archives'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey('overseas_tasks.id'), unique=True)
    versions: Mapped[list] = mapped_column(JSON)
    product_name: Mapped[str | None] = mapped_column(String(80))
    brand: Mapped[str | None] = mapped_column(String(60))
    platform: Mapped[str | None] = mapped_column(String(40))
    skus: Mapped[list | None] = mapped_column(JSON)
    sku_search: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    designer_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)


class ArchiveAsset(Timestamps, Base):
    __tablename__ = 'overseas_archive_assets'
    __table_args__ = (UniqueConstraint('archive_id', 'source_version'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    archive_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_archives.id'), index=True)
    source_version: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    sku: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    bucket: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
