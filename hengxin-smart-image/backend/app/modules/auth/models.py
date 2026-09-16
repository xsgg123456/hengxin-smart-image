"""Durable identity bindings and opaque browser sessions."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.resource_models import Timestamps


class UserIdentityRecord(Timestamps, Base):
    __tablename__ = 'user_identities'
    __table_args__ = (
        UniqueConstraint('provider', 'corp_id', 'provider_user_id', name='uq_user_identity_provider'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    corp_id: Mapped[str] = mapped_column(String(200))
    provider_user_id: Mapped[str] = mapped_column(String(200))
    union_id: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(200), default='')


class AuthSessionRecord(Timestamps, Base):
    __tablename__ = 'auth_sessions'

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoleAssignmentRecord(Timestamps, Base):
    __tablename__ = 'role_assignments'
    __table_args__ = (
        UniqueConstraint('user_id', name='uq_role_assignment_user'),
        CheckConstraint("role IN ('super_admin','design_manager','designer','operator')"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    role: Mapped[str] = mapped_column(String(32))
    assigned_by: Mapped[UUID | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))


class AuthLoginStateRecord(Timestamps, Base):
    __tablename__ = 'auth_login_states'

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    return_path: Mapped[str] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
