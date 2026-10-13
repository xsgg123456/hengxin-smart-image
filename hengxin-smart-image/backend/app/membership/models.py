"""Column mixins only: importing this module never registers either business metadata."""
from uuid import UUID, uuid4

from sqlalchemy import Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.timestamps import Timestamps


class ApplicationFields(Timestamps):
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    corp_id: Mapped[str] = mapped_column(String(200))
    provider_user_id: Mapped[str] = mapped_column(String(200))
    union_id: Mapped[str | None] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(200), default='')
    status: Mapped[str] = mapped_column(String(20), default='pending')
    version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    reason: Mapped[str | None] = mapped_column(String(1000))


class EventFields(Timestamps):
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(32))
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
