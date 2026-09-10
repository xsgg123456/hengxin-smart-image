"""Durable object deletion receipt; no foreign key to already collected metadata."""
from uuid import UUID, uuid4
from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.resource_models import Timestamps


class CleanupObject(Timestamps, Base):
    __tablename__ = 'cleanup_objects'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    bucket: Mapped[str] = mapped_column(String(63))
    object_key: Mapped[str] = mapped_column(String(200), unique=True)
