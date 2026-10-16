from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base
from app.db.timestamps import Timestamps


class ExecutionGate(Timestamps, Base):
    __tablename__ = 'execution_gate'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
