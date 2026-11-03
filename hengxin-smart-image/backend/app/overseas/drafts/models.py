from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps
from app.overseas.db import Base


class RequirementDraft(Timestamps, Base):
    __tablename__ = 'overseas_requirement_drafts'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'), unique=True)
    epoch: Mapped[UUID] = mapped_column(Uuid, unique=True, default=uuid4)
    version: Mapped[int] = mapped_column(Integer, default=1)
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[dict | None] = mapped_column(JSON)
    submit_key: Mapped[str] = mapped_column(String(128), default=lambda: str(uuid4()))
    last_submitted_task_id: Mapped[UUID | None] = mapped_column(Uuid)
    last_submitted_key: Mapped[str | None] = mapped_column(String(128))


class DraftMaterial(Timestamps, Base):
    __tablename__ = 'overseas_draft_materials'
    __table_args__ = (UniqueConstraint('draft_id', 'material_id'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    draft_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_requirement_drafts.id'))
    epoch: Mapped[UUID] = mapped_column(Uuid, index=True)
    material_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_materials.id'), unique=True)


class DraftImport(Timestamps, Base):
    __tablename__ = 'overseas_draft_imports'
    __table_args__ = (UniqueConstraint('draft_id', 'epoch', 'source_file_id'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    draft_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_requirement_drafts.id'), index=True)
    epoch: Mapped[UUID] = mapped_column(Uuid)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'))
    sku: Mapped[str] = mapped_column(String(80))
    requirement_id: Mapped[str] = mapped_column(String(200))
    source_file_id: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(300))
    material_id: Mapped[UUID | None] = mapped_column(ForeignKey('overseas_materials.id', ondelete='SET NULL'))
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
