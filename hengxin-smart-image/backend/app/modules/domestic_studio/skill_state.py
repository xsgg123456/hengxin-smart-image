"""Domestic availability layered over verified Skill files, under the same gate."""
from fastapi import HTTPException
from sqlalchemy import Boolean, CheckConstraint, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.timestamps import Timestamps
from app.models import Base
from .bindings import assert_unbound, lock_admission
from .installed_skills import DomesticInstalledSkills


class DomesticSkillState(Timestamps, Base):
    __tablename__ = 'domestic_studio_skill_states'
    __table_args__ = (CheckConstraint('version >= 1'),)
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


def listing(session: Session, catalog: DomesticInstalledSkills):
    states = {state.name: state for state in session.scalars(
        select(DomesticSkillState).execution_options(populate_existing=True))}
    return [{**item, 'enabled': states[item['name']].enabled if item['name'] in states else False,
             'version': states[item['name']].version if item['name'] in states else 1,
             'platforms': []} for item in catalog.list()]


def set_availability(session: Session, catalog: DomesticInstalledSkills, skill_id: str,
                     enabled: bool, expected_version: int):
    """The HTTP caller must authorize a domestic super-admin; caller commits."""
    if not isinstance(enabled, bool):
        raise HTTPException(422, 'Skill 开关必须为布尔值')
    lock_admission(session)
    item = next((item for item in catalog.list() if item['id'] == skill_id), None)
    if item is None:
        raise HTTPException(404, 'Skill 不在当前安装目录中')
    state = session.scalar(select(DomesticSkillState).where(
        DomesticSkillState.name == item['name']).execution_options(populate_existing=True))
    if (state.version if state else 1) != expected_version:
        raise HTTPException(409, 'Skill 状态已变化，请刷新后重试')
    if not enabled:
        assert_unbound(session, skill_id)
    if state is None:
        state = DomesticSkillState(name=item['name'], enabled=enabled, version=2)
        session.add(state)
    else:
        state.enabled = enabled
        state.version += 1
    session.flush()
    return listing(session, catalog)


def freeze_enabled(session: Session, catalog: DomesticInstalledSkills, skill_id: str):
    """Freeze only an installed, enabled package while holding admission gate."""
    lock_admission(session)
    skill = catalog.freeze(skill_id)
    state = session.scalar(select(DomesticSkillState).where(
        DomesticSkillState.name == skill['name']).execution_options(populate_existing=True))
    if state is None or not state.enabled:
        raise HTTPException(422, 'Skill 已停用，请联系管理员')
    return {'skill': skill}
