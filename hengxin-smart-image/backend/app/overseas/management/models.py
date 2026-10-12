from uuid import UUID, uuid4
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.timestamps import Timestamps
from app.overseas.db import Base


class Skill(Timestamps, Base):
    __tablename__ = 'overseas_skills'
    __table_args__ = (CheckConstraint("stage IN ('analysis','generation','revision')"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    stage: Mapped[str] = mapped_column(String(20))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    current_version: Mapped[int] = mapped_column(Integer, default=1)


class SkillVersion(Timestamps, Base):
    __tablename__ = 'overseas_skill_versions'
    __table_args__ = (UniqueConstraint('skill_id', 'version'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    skill_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_skills.id'))
    version: Mapped[int] = mapped_column(Integer)
    files: Mapped[dict] = mapped_column(JSON)


class Settings(Timestamps, Base):
    __tablename__ = 'overseas_settings'
    __table_args__ = (CheckConstraint('id = 1'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    values: Mapped[dict] = mapped_column(JSON, default=dict)


class Audit(Timestamps, Base):
    __tablename__ = 'overseas_management_audit'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey('overseas_members.id'))
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(100))
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
