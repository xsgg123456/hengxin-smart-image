"""Installed packages remain immutable; availability is independently durable."""
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.overseas.execution.queue import lock_gate
from app.overseas.tasks.service import lock_actor
from app.overseas.permissions import has_full_access_grant
from .installed_catalog import listing
from .models import Audit, InstalledSkillAvailability


def can_toggle(actor):
    owner = getattr(get_settings(), 'skill_toggle_owner_id', None)
    return has_full_access_grant(actor) or (owner is not None and actor is not None and actor.id == owner)


def states(session):
    return {row.id: row for row in session.scalars(select(InstalledSkillAvailability)
            .execution_options(populate_existing=True))}


def list_skills(session, actor):
    current = states(session)
    return {'items': [{**item, 'enabled': current[item['name']].enabled if item['name'] in current else False,
                      'version': current[item['name']].version if item['name'] in current else 1}
                     for item in listing()], 'canToggle': can_toggle(actor)}


def enabled_listing(session):
    current = states(session)
    return [item for item in listing() if item['name'] in current and current[item['name']].enabled]


def require_enabled(session, name):
    row = session.scalar(select(InstalledSkillAvailability).where(InstalledSkillAvailability.id == name)
                         .execution_options(populate_existing=True))
    if row is None or not row.enabled:
        raise HTTPException(422, '所选 Skill 已关闭，请重新选择后发送')


def set_availability(session, actor, skill_id, body):
    actor = lock_actor(session, actor, 'skills.manage')
    if not can_toggle(actor):
        raise HTTPException(403, '仅指定账号可调整 Skill 开关')
    # Same gate as new job admission: disable and freeze have a single ordering.
    lock_gate(session)
    before_catalog = list_skills(session, actor)
    item = next((item for item in before_catalog['items'] if item['id'] == str(skill_id)), None)
    if item is None:
        raise HTTPException(404, 'Skill 不在当前安装目录中')
    if body.version != item['version']:
        raise HTTPException(409, 'Skill 状态已变化，请刷新后重试')
    row = session.get(InstalledSkillAvailability, item['name'])
    if row is None:
        row = InstalledSkillAvailability(id=item['name'])
        session.add(row)
    before = {'enabled': item['enabled'], 'version': item['version']}
    row.enabled, row.version = body.enabled, item['version'] + 1
    row.updated_at = utcnow()
    session.add(Audit(actor_id=actor.id, action='skill.availability', target=item['name'],
                      before=before, after={'enabled': row.enabled, 'version': row.version}))
    session.flush()
    result = list_skills(session, actor)
    session.commit()
    return result
