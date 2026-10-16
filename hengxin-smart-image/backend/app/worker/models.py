from datetime import datetime
from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base, utcnow


class WorkerHeartbeat(Base):
    __tablename__ = 'worker_heartbeats'
    node: Mapped[str] = mapped_column(String(200), primary_key=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    state: Mapped[str] = mapped_column(String(20), default='unknown')
    dependencies: Mapped[dict] = mapped_column(JSON, default=dict)
