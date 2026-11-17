"""Domestic tasks are independent of worker identities and physical storage."""
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.timestamps import Timestamps
from app.models import Base


class Task(Timestamps, Base):
    __tablename__ = 'domestic_studio_tasks'
    __table_args__ = (
        UniqueConstraint('id', 'owner_id', 'workspace', name='uq_domestic_task_owner_workspace'),
        CheckConstraint("workspace IN ('camera','case','product','scene','phone')"),
        CheckConstraint('length(trim(name)) BETWEEN 1 AND 60'),
        CheckConstraint("deletion_status IS NULL OR deletion_status IN ('deleting','delete_failed','deleted')"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), index=True)
    workspace: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(60))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    deletion_status: Mapped[str | None] = mapped_column(String(20))
    deletion_error: Mapped[str | None] = mapped_column(Text)
    deletion_manifest: Mapped[list] = mapped_column(JSON, default=list, server_default='[]')


class TaskRequest(Timestamps, Base):
    __tablename__ = 'domestic_studio_task_requests'
    __table_args__ = (UniqueConstraint('user_id', 'operation', 'target', 'key'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    operation: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(80))
    key: Mapped[str] = mapped_column(String(128))
    body_hash: Mapped[str] = mapped_column(String(64))
    task_id: Mapped[UUID] = mapped_column(ForeignKey('domestic_studio_tasks.id'))
