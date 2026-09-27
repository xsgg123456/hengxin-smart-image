"""Durable disk admission; execution leases never own or expire these records."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Integer, JSON, String, Uuid, event
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.resource_models import Timestamps


class CapacityGate(Timestamps, Base):
    __tablename__ = 'capacity_gate'
    __table_args__ = (CheckConstraint('id = 1'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    floor_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    api_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    cli_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    free_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    sample_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    volumes: Mapped[dict] = mapped_column(JSON, default=dict)


class CapacityReservation(Timestamps, Base):
    __tablename__ = 'capacity_reservations'
    __table_args__ = (CheckConstraint('bytes > 0'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    kind: Mapped[str] = mapped_column(String(8))
    owner_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    bytes: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(16), default='held', index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


@event.listens_for(CapacityGate.__table__, 'after_create')
def seed_gate(target, connection, **kwargs):
    connection.execute(target.insert().values(id=1, enabled=False))
