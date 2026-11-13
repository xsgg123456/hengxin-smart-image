"""Domestic authorization around the shared immutable Skill publisher."""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.overseas.management import installed_catalog as catalog
from app.overseas.management import skill_cleanup as cleanup
from app.overseas.management import skill_publication as shared
from app.modules.auth.member_policy import lock_permissions
from app.resource_models import UserRecord
from .bindings import assert_unbound, lock_admission
from .models import SkillPublicationAudit
from .skill_state import DomesticSkillState
from . import skill_references
from . import protected as protection


def authorize(session, actor_id):
    # Match domestic membership updates: permission changes and writes must
    # serialize before taking the execution gate.
    lock_permissions(session)
    actor = session.scalar(select(UserRecord).where(UserRecord.id == UUID(str(actor_id)))
                           .with_for_update().execution_options(populate_existing=True))
    if (actor is None or actor.status != 'active' or actor.role != 'super_admin'
            or actor.directory_state != 'enrolled'
            or (protection.enabled(get_settings()) and actor.identity_source == 'development')):
        raise HTTPException(403, '仅超级管理员可管理国内 Skill')
    return actor


def recover(store, session):
    return shared.recover(store, session, audit_model=SkillPublicationAudit, gate=lock_admission)


def committed_transfer(session, actor_id, transfer_id):
    return shared.committed_transfer(session, actor_id, transfer_id, audit_model=SkillPublicationAudit)


def transfer_status(store, session, state):
    return shared.transfer_status(store, session, state, audit_model=SkillPublicationAudit)


def install(store, session, actor_id, transfer_id, base_release):
    actor = authorize(session, actor_id)
    state = store.load(transfer_id, actor_id)
    if state['status'] == 'installed':
        return state
    prior = committed_transfer(session, actor.id, transfer_id)
    if prior:
        state.update(status='installed', release=prior.after['release'], error=None)
        return store.save(state)
    if state['status'] not in ('validated', 'failed') or not state.get('package'):
        raise HTTPException(409, '请先完成服务端校验')
    lock_admission(session)
    release, items = catalog.read_catalog(store.installed_root, store.protected)
    if base_release != release or state['baseRelease'] != release:
        raise HTTPException(409, '安装目录已变化，请重新校验并确认差异')
    checked = store.validate(transfer_id, actor_id)
    name = checked['package']['name']
    before = next((item for item in items if item['name'] == name), None)
    item = dict(checked['package'], entries=checked['entries'], rootName=checked['rootName'])
    updated = [row for row in items if row['name'] != name] + [item]
    before_bytes = cleanup.footprint(store)
    pinned, _ = skill_references.pinned(session, store, {name})
    retained = pinned | {(entry['name'], entry['checksum']) for entry in updated}
    new_release = shared.prepare_release(store, updated, checked)
    cleanup_plan = cleanup.plan(store, {name}, retained, before_bytes, 0, transfer_id)
    row = session.get(DomesticSkillState, name, populate_existing=True)
    if before is None:
        if row is None:
            row = DomesticSkillState(name=name, enabled=False, version=1)
            session.add(row)
        else:
            row.enabled, row.version = False, row.version + 1
    shared.switch(store, session, actor, 'skill.install' if before is None else 'skill.update', name,
                  {'release': release, 'checksum': before['checksum'] if before else None},
                  {'release': new_release, 'checksum': item['checksum'], 'transferId': transfer_id},
                  new_release, cleanup_plan, audit_model=SkillPublicationAudit, gate=lock_admission)
    checked.update(status='installed', release=new_release)
    return store.save(checked)


def delete(store, session, actor_id, skill_id, body):
    actor = authorize(session, actor_id)
    lock_admission(session)
    release, items = catalog.read_catalog(store.installed_root, store.protected)
    item = next((item for item in items if catalog.identity(item['name']) == str(skill_id)), None)
    if item is None:
        rows = session.scalars(select(SkillPublicationAudit).where(
            SkillPublicationAudit.actor_id == actor.id, SkillPublicationAudit.action == 'skill.delete')
            .order_by(SkillPublicationAudit.created_at.desc()))
        prior = next((row for row in rows if catalog.identity(row.target) == str(skill_id)
                      and row.before == body.model_dump()), None)
        if prior:
            return {'deleted': True, 'release': prior.after['release'],
                    'reclaimedBytes': prior.after.get('reclaimedBytes', 0)}
        raise HTTPException(404, 'Skill 不在当前安装目录中')
    assert_unbound(session, str(skill_id))
    pinned, busy = skill_references.pinned(session, store, {item['name']})
    if busy:
        raise HTTPException(409, '仍有排队或运行中的任务使用此 Skill，请等待结束后重试')
    row = session.get(DomesticSkillState, item['name'], populate_existing=True)
    version = row.version if row else 1
    if body.release != release or body.checksum != item['checksum'] or body.version != version:
        raise HTTPException(409, 'Skill 内容或状态已变化，请刷新后重新确认删除')
    updated = [entry for entry in items if entry['name'] != item['name']]
    before_bytes = cleanup.footprint(store)
    retained = pinned | {(entry['name'], entry['checksum']) for entry in updated}
    new_release = shared.prepare_release(store, updated)
    cleanup_plan = cleanup.plan(store, {item['name']}, retained, before_bytes)
    if row:
        row.enabled, row.version = False, version + 1
    result = shared.switch(store, session, actor, 'skill.delete', item['name'],
                           {'release': release, 'checksum': item['checksum'], 'version': version},
                           {'release': new_release, 'deleted': True}, new_release, cleanup_plan,
                           audit_model=SkillPublicationAudit, gate=lock_admission)
    return {'deleted': True, 'release': new_release, 'reclaimedBytes': result['reclaimedBytes']}
