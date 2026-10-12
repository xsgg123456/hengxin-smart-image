"""Overseas task persistence, independent from domestic execution records."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps
from app.overseas.db import Base


class Task(Timestamps, Base):
    __tablename__ = 'overseas_tasks'
    __table_args__ = (CheckConstraint('version >= 1'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80))
    product_name: Mapped[str] = mapped_column(String(80))
    brand: Mapped[str] = mapped_column(String(60))
    platform: Mapped[str] = mapped_column(String(40))
    market: Mapped[str] = mapped_column(String(60))
    remarks: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'), index=True)
    designer_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'), index=True)
    status: Mapped[str] = mapped_column(String(40), default='created')
    version: Mapped[int] = mapped_column(Integer, default=1)


class TaskSku(Timestamps, Base):
    __tablename__ = 'overseas_task_skus'
    __table_args__ = (UniqueConstraint('task_id', 'code_key'), UniqueConstraint('task_id', 'position'))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    code: Mapped[str] = mapped_column(String(80))
    code_key: Mapped[str] = mapped_column(String(240))
    position: Mapped[int] = mapped_column(Integer)


class TaskEvent(Timestamps, Base):
    __tablename__ = 'overseas_task_events'
    __table_args__ = (UniqueConstraint('task_id', 'version'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'))
    actor_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    before_designer_id: Mapped[UUID | None] = mapped_column(ForeignKey('overseas_members.id'))
    after_designer_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'))
    version: Mapped[int] = mapped_column(Integer)


class TaskRequest(Timestamps, Base):
    __tablename__ = 'overseas_task_requests'
    __table_args__ = (UniqueConstraint('user_id', 'operation', 'target', 'key'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'))
    operation: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(128))
    body_hash: Mapped[str] = mapped_column(String(64))
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'))


class TaskOutbox(Timestamps, Base):
    __tablename__ = 'overseas_task_outbox'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_task_events.id'), unique=True)
    topic: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
