"""Overseas-only identity bindings; no domestic model registrations."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.timestamps import Timestamps
from app.overseas.db import Base

ROLES = ('operator', 'operator_manager', 'designer', 'design_manager', 'super_admin')


class Member(Timestamps, Base):
    __tablename__ = 'overseas_members'
    __table_args__ = (
        UniqueConstraint('corp_id', 'provider_user_id', name='uq_overseas_member_identity'),
        CheckConstraint("status IN ('active','pending','disabled')"),
        CheckConstraint("directory_state IN ('enrolled','legacy_unconfirmed')",
                        name='ck_overseas_members_directory_state'),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    corp_id: Mapped[str] = mapped_column(String(200))
    provider_user_id: Mapped[str] = mapped_column(String(200))
    union_id: Mapped[str | None] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(200), default='')
    status: Mapped[str] = mapped_column(String(20), default='pending')
    version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    directory_state: Mapped[str] = mapped_column(String(32), default='enrolled', server_default='enrolled')


class MemberRole(Timestamps, Base):
    __tablename__ = 'overseas_member_roles'
    __table_args__ = (
        UniqueConstraint('user_id', name='uq_overseas_member_single_role'),
        CheckConstraint("role IN ('operator','operator_manager','designer','design_manager','super_admin')"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(32))


class BusinessSession(Timestamps, Base):
    __tablename__ = 'overseas_sessions'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    identity_session_id: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
