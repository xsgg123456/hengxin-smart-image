"""A domestic-only mapping; Skill packages remain in their own catalog."""
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.timestamps import Timestamps
from app.models import Base


class WorkspaceBinding(Timestamps, Base):
    __tablename__ = 'domestic_studio_skill_bindings'
    __table_args__ = (CheckConstraint("workspace IN ('camera','case','product','scene','phone')"),)

    workspace: Mapped[str] = mapped_column(String(20), primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(100), nullable=False)


class SkillPublicationAudit(Timestamps, Base):
    """Durable record used to recover an interrupted domestic publication."""
    __tablename__ = 'domestic_studio_skill_publication_audit'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(100))
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)


class SkillExecutionReference(Timestamps, Base):
    """Pin the exact immutable package owned by a domestic Studio job."""
    __tablename__ = 'domestic_studio_skill_references'
    job_id: Mapped[UUID] = mapped_column(ForeignKey('job_records.id', ondelete='CASCADE'), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    release: Mapped[str] = mapped_column(String(64), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
