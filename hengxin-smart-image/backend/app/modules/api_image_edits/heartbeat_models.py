"""Independent API worker observations, never inferred from business queue rows."""
from datetime import datetime
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base, utcnow
from app.resource_models import Timestamps


class ApiWorkerHeartbeat(Timestamps, Base):
    __tablename__ = 'api_worker_heartbeats'
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    state: Mapped[str] = mapped_column(String(20), default='unknown')
    capacity: Mapped[int | None] = mapped_column(Integer)
