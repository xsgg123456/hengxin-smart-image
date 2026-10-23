"""Task-owned conversations; generated pictures are immutable storage versions."""
from uuid import UUID, uuid4
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps
from app.overseas.db import Base


class Conversation(Timestamps, Base):
    __tablename__ = 'overseas_studio_conversations'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    name: Mapped[str] = mapped_column(String(30), default='新会话', server_default='新会话')
    version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
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
    delivery_error: Mapped[str | None] = mapped_column(Text)
    event_offset: Mapped[int] = mapped_column(Integer, default=0)
    event_session_id: Mapped[str | None] = mapped_column(String(128))
    event_invalid: Mapped[bool] = mapped_column(Boolean, default=False)
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False)


class ConversationDeletion(Timestamps, Base):
    __tablename__ = 'overseas_studio_conversation_deletions'
    conversation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(20), default='deleting', index=True)
    error: Mapped[str | None] = mapped_column(String(200))
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)


class Upload(Timestamps, Base):
    __tablename__ = 'overseas_studio_uploads'
    conversation_id: Mapped[UUID | None] = mapped_column(ForeignKey('overseas_studio_conversations.id'), index=True)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    bucket: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)


class MaterialVisibility(Timestamps, Base):
    __tablename__ = 'overseas_studio_material_visibility'
    scope: Mapped[str] = mapped_column(String(36), default='', server_default='')
    __table_args__ = (UniqueConstraint('task_id', 'checksum', 'scope'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    checksum: Mapped[str] = mapped_column(String(64))
    hidden: Mapped[bool] = mapped_column(Boolean, default=True)


class Picture(Timestamps, Base):
    __tablename__ = 'overseas_studio_pictures'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    turn_id: Mapped[UUID | None] = mapped_column(ForeignKey('overseas_studio_turns.id'), index=True)
    origin_turn_id: Mapped[UUID | None] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    bucket: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    sku: Mapped[str | None] = mapped_column(String(80))
    source_path: Mapped[str | None] = mapped_column(Text)


class Transcript(Timestamps, Base):
    __tablename__ = 'overseas_studio_transcript'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    turn_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_studio_turns.id'), index=True)
    item_id: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20))
