from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps
from app.overseas.db import Base


class Plan(Timestamps, Base):
    __tablename__ = 'overseas_plans'
    __table_args__ = (UniqueConstraint('task_id', 'version'), CheckConstraint('version >= 1'),
                     CheckConstraint("status IN ('pending','ready','confirmed')"))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    job_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_jobs.id'), unique=True)
    feedback: Mapped[str] = mapped_column(Text, default='')
    content: Mapped[dict | None] = mapped_column(JSON)
