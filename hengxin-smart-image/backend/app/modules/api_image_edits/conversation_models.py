"""API item conversations are independent of batch CLI task records."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.resource_models import Timestamps


class Conversation(Timestamps, Base):
    __tablename__ = 'api_edit_conversations'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(ForeignKey('api_image_items.id'), unique=True)
    session_id: Mapped[str | None] = mapped_column(String(128))
    last_event_id: Mapped[int] = mapped_column(Integer, default=0)


class ConversationTurn(Timestamps, Base):
    __tablename__ = 'api_edit_turns'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey('api_edit_conversations.id'), index=True)
    job_id: Mapped[UUID] = mapped_column(ForeignKey('job_records.id'), unique=True)
    operator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(String(20), default='queued')
    text: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSON)
    base_version: Mapped[int | None] = mapped_column(Integer)
    base_turn_id: Mapped[UUID | None] = mapped_column(ForeignKey('api_edit_turns.id'))
    base_file_id: Mapped[UUID] = mapped_column(ForeignKey('api_image_files.id'))
    annotation_id: Mapped[UUID | None] = mapped_column(ForeignKey('api_image_files.id'))
    candidate_id: Mapped[UUID | None] = mapped_column(ForeignKey('api_image_files.id'))
    adopted_version: Mapped[int | None] = mapped_column(Integer)
    messages: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(String(300))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    process_identity: Mapped[dict | None] = mapped_column(JSON)


class ConversationEvent(Timestamps, Base):
    __tablename__ = 'api_edit_events'
    __table_args__ = (UniqueConstraint('conversation_id', 'number'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey('api_edit_conversations.id'), index=True)
    turn_id: Mapped[UUID] = mapped_column(ForeignKey('api_edit_turns.id'))
    number: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
