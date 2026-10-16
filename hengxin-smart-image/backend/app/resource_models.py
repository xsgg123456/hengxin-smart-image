"""Stable identities and private resource metadata; development identities stay distinct."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, utcnow
from app.db.timestamps import Timestamps


class UserRecord(Timestamps, Base):
    __tablename__ = 'users'
    __table_args__ = (
        CheckConstraint("status IN ('active','pending','disabled')"),
        CheckConstraint("role IN ('super_admin','design_manager','designer','operator')"),
        CheckConstraint("directory_state IN ('enrolled','legacy_unconfirmed')",
                        name='ck_users_directory_state'),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    identity_source: Mapped[str] = mapped_column(String(20))
    directory_state: Mapped[str] = mapped_column(String(32), default='enrolled', server_default='enrolled')




