from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.timestamps import Timestamps
from app.overseas.db import Base


class MemberAudit(Timestamps, Base):
    __tablename__ = 'overseas_member_audits'

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    member_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'), index=True)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey('overseas_members.id'))
    action: Mapped[str] = mapped_column(String(32))
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
