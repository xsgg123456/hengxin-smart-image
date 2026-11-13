"""Private domestic Studio turns and the files explicitly owned by them."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.timestamps import Timestamps
from app.models import Base


class Turn(Timestamps, Base):
    __tablename__ = 'domestic_studio_turns'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey('domestic_studio_conversations.id'), index=True)
    job_id: Mapped[UUID] = mapped_column(ForeignKey('job_records.id'), unique=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    text: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSON)
    output_intents: Mapped[dict] = mapped_column(JSON, default=dict, server_default='{}')
    reply: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    recovery_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    process_identity: Mapped[dict | None] = mapped_column(JSON)
    event_offset: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    event_session_id: Mapped[str | None] = mapped_column(String(128))
    event_invalid: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Upload(Timestamps, Base):
    __tablename__ = 'domestic_studio_uploads'
    __table_args__ = (CheckConstraint("status IN ('ready', 'uploading')"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey('domestic_studio_conversations.id'), index=True)
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    bucket: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    status: Mapped[str] = mapped_column(String(16), default='ready', server_default='ready')


class Picture(Timestamps, Base):
    __tablename__ = 'domestic_studio_pictures'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    turn_id: Mapped[UUID] = mapped_column(ForeignKey('domestic_studio_turns.id'), index=True)
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    bucket: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    source_path: Mapped[str | None] = mapped_column(Text)


class OutputFile(Timestamps, Base):
    __tablename__ = 'domestic_studio_output_files'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    turn_id: Mapped[UUID] = mapped_column(ForeignKey('domestic_studio_turns.id'), index=True)
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    bucket: Mapped[str] = mapped_column(String(200))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    source_path: Mapped[str] = mapped_column(Text)


class Transcript(Timestamps, Base):
    __tablename__ = 'domestic_studio_transcript'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    turn_id: Mapped[UUID] = mapped_column(ForeignKey('domestic_studio_turns.id'), index=True)
    item_id: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20))
