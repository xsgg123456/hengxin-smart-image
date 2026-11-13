"""Domestic workspaces and their creator-owned conversations."""
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.timestamps import Timestamps
from app.models import Base


WORKSPACE_CHECK = "workspace IN ('camera','case','product','scene','phone')"


class Workspace(Timestamps, Base):
    __tablename__ = 'domestic_studio_workspaces'
    __table_args__ = (CheckConstraint(WORKSPACE_CHECK),)

    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), primary_key=True)
    workspace: Mapped[str] = mapped_column(String(20), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')


class Conversation(Timestamps, Base):
    __tablename__ = 'domestic_studio_conversations'
    __table_args__ = (
        ForeignKeyConstraint(['owner_id', 'workspace'],
                             ['domestic_studio_workspaces.owner_id', 'domestic_studio_workspaces.workspace']),
        CheckConstraint(WORKSPACE_CHECK),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    workspace: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(30))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    session_id: Mapped[str | None] = mapped_column(String(128))


class ConversationRequest(Timestamps, Base):
    """Idempotency receipts do not make a deleted conversation readable."""
    __tablename__ = 'domestic_studio_conversation_requests'
    __table_args__ = (UniqueConstraint('user_id', 'operation', 'target', 'key'),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    operation: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(80))
    key: Mapped[str] = mapped_column(String(128))
    body_hash: Mapped[str] = mapped_column(String(64))
    conversation_id: Mapped[UUID] = mapped_column(Uuid)


class ConversationDeletion(Timestamps, Base):
    """Durable ownership proof and retry state for deleting a private session."""
    __tablename__ = 'domestic_studio_conversation_deletions'
    conversation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), index=True)
    workspace: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), index=True)
    manifest: Mapped[dict] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
