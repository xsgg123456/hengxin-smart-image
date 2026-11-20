from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, LargeBinary, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.timestamps import Timestamps
from app.overseas.db import Base


class FeedbackGrant(Timestamps, Base):
    __tablename__ = 'overseas_feedback_grants'
    id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id', ondelete='CASCADE'), primary_key=True)


class Feedback(Timestamps, Base):
    __tablename__ = 'overseas_feedback'
    __table_args__ = (
        CheckConstraint("status IN ('pending','processing','resolved')"),
        CheckConstraint("status != 'resolved' OR length(trim(public_reply)) > 0"),
        CheckConstraint('version >= 1'),
        Index('ix_overseas_feedback_owner_date', 'submitter_id', 'created_at'),
        Index('ix_overseas_feedback_status_date', 'status', 'created_at'),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    submitter_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'))
    submitter_name: Mapped[str] = mapped_column(String(200))
    question: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(500))
    task_name: Mapped[str | None] = mapped_column(String(200))
    sku: Mapped[str | None] = mapped_column(String(8099))
    screenshot_type: Mapped[str | None] = mapped_column(String(20))
    screenshot: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    status: Mapped[str] = mapped_column(String(16), default='pending')
    public_reply: Mapped[str] = mapped_column(Text, default='')
    internal_note: Mapped[str] = mapped_column(Text, default='', deferred=True)
    version: Mapped[int] = mapped_column(default=1)
