from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.resource_models import Timestamps


class SystemSettings(Timestamps, Base):
    __tablename__ = 'system_settings'
    __table_args__ = (CheckConstraint('id = 1'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    values: Mapped[dict] = mapped_column(JSON, default=dict)


class SettingsAuditRecord(Timestamps, Base):
    __tablename__ = 'settings_audit'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    operator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    operator_name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, unique=True)
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    fields: Mapped[list] = mapped_column(JSON)
