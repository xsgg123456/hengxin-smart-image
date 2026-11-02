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
                      'platforms': current[item['name']].platforms if item['name'] in current else [],
                      'version': current[item['name']].version if item['name'] in current else 1}
                     for item in listing()], 'canToggle': can_toggle(actor), 'canManagePlatforms': True}


def enabled_listing(session, platform):
    current = states(session)
    return [item for item in listing() if item['name'] in current and current[item['name']].enabled
            and platform in current[item['name']].platforms]


def require_enabled(session, name, platform=None):
    row = session.scalar(select(InstalledSkillAvailability).where(InstalledSkillAvailability.id == name)
                         .execution_options(populate_existing=True))
    if row is None or not row.enabled:
        raise HTTPException(422, '所选 Skill 已关闭，请重新选择后发送')
    if platform is not None and platform not in row.platforms:
        raise HTTPException(422, '所选 Skill 不属于当前任务平台，请重新选择或不选 Skill 后发送')


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


def set_platforms(session, actor, body):
    actor = lock_actor(session, actor, 'skills.manage')
    # Share ordering and revision with switches and new round admission.
    lock_gate(session)
    catalog = {item['id']: item for item in list_skills(session, actor)['items']}
    for change in body.items:
        item = catalog.get(str(change.id))
        if item is None:
            raise HTTPException(404, 'Skill 不在当前安装目录中')
        if change.version != item['version']:
            raise HTTPException(409, 'Skill 状态或平台已变化，请刷新后重试')
    # Validate the complete batch before touching any rows or audit records.
    for change in body.items:
        item = catalog[str(change.id)]
        row = session.get(InstalledSkillAvailability, item['name'])
        if row is None:
            row = InstalledSkillAvailability(id=item['name'], enabled=item['enabled'])
            session.add(row)
        before = {'platforms': item['platforms'], 'version': item['version']}
        row.platforms, row.version = list(change.platforms), item['version'] + 1
        row.updated_at = utcnow()
        session.add(Audit(actor_id=actor.id, action='skill.platforms', target=item['name'],
            before=before, after={'platforms': row.platforms, 'version': row.version}))
    session.flush()
    result = list_skills(session, actor)
    session.commit()
    return result
