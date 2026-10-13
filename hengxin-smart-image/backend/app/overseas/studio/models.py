"""Task-owned conversations; generated pictures are immutable storage versions."""
from uuid import UUID, uuid4
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps
from app.overseas.db import Base


class Conversation(Timestamps, Base):
    __tablename__ = 'overseas_studio_conversations'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), unique=True)
    session_id: Mapped[str | None] = mapped_column(String(128))


class Turn(Timestamps, Base):
    __tablename__ = 'overseas_studio_turns'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_studio_conversations.id'))
    job_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_jobs.id'), unique=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'))
    text: Mapped[str] = mapped_column(Text)
    skill_name: Mapped[str | None] = mapped_column(String(100))
    attachment_ids: Mapped[list] = mapped_column(JSON, default=list)
    reference_ids: Mapped[list] = mapped_column(JSON, default=list)
    reply: Mapped[str | None] = mapped_column(Text)
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False)


class Upload(Timestamps, Base):
    __tablename__ = 'overseas_studio_uploads'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    bucket: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)


class Picture(Timestamps, Base):
    __tablename__ = 'overseas_studio_pictures'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    turn_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_studio_turns.id'), index=True)
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    bucket: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    sku: Mapped[str | None] = mapped_column(String(80))
