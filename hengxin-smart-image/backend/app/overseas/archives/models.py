from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps
from app.overseas.db import Base


class Archive(Timestamps, Base):
    __tablename__ = 'overseas_archives'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_tasks.id'), unique=True)
    versions: Mapped[list] = mapped_column(JSON)
