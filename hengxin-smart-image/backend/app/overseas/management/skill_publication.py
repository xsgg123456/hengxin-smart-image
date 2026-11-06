"""Root-only immutable publication, DB admission ordering and crash recovery."""
import json
import os
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.auth.models import Member
from app.overseas.execution.queue import lock_gate
from app.overseas.tasks.service import lock_actor
from . import installed_catalog as catalog
from .installed_tree import digest, read_file
from . import skill_cleanup as cleanup, skill_references as references
from . import skill_preparation as preparation
from .skill_objects import prepare_release as prepare_objects
from .models import Audit, InstalledSkillAvailability
from .skill_transfer_store import atomic_json, sync_directory
from .skills import can_toggle


def authorize(session, actor_id):
    actor = session.get(Member, UUID(str(actor_id)))
    if actor is None:
        raise HTTPException(403, '发布请求身份无效')
    actor = lock_actor(session, actor, 'skills.manage')
    if not can_toggle(actor):
        raise HTTPException(403, '仅指定账号可上传、更新或删除 Skill')
    return actor


def prepare_release(store, items, replacement=None):
    sources = {replacement['package']['name']: store.directory(replacement['id']) / 'package'} if replacement else None
    return prepare_objects(store.installed_root, items, sources, protected=store.protected)


def finish(store, session, pending, audit):
    if audit and pending.get('cleanup') and not audit.after.get('cleanupComplete'):
        reclaimed = cleanup.execute(store, pending['cleanup'])
        audit.after = dict(audit.after, cleanupComplete=True, reclaimedBytes=reclaimed,
                           afterBytes=cleanup.footprint(store), libraryAfterBytes=cleanup.library_footprint(store))
        session.commit()
    if audit and audit.after.get('cleanupComplete'):
        preparation.clear(store)
    (store.installed_root / '.pending.json').unlink()
    sync_directory(store.installed_root)


def recover(store, session):
    """Caller holds the publisher lock; DB gate excludes new round admission."""
    journal = store.installed_root / '.pending.json'
    if not journal.exists():
        return
    lock_gate(session)
    pending = json.loads(read_file(journal, protected=store.protected))
    audit = session.get(Audit, UUID(pending['audit']))
    release = pending['after'] if audit else pending['before']
    pointer = store.installed_root / 'current.json'
    if release:
        directory, manifest = catalog.release_manifest(store.installed_root, release, store.protected)
        for item in manifest['items']:
            catalog.verify_package(directory, item, store.protected)
        atomic_json(pointer, {'release': release})
    elif pointer.exists():
        pointer.unlink()
    if not release:
        # First ever publication failed: retain frozen releases, publish a valid empty catalog.
        empty = {'schema': 1, 'items': []}
        release = digest(empty)
        folder = store.installed_root / 'releases' / release
        folder.mkdir(exist_ok=True)
        atomic_json(folder / 'manifest.json', empty)
        atomic_json(pointer, {'release': release})
    finish(store, session, pending, audit)
    session.commit()


def committed_transfer(session, actor_id, transfer_id):
    rows = session.scalars(select(Audit).where(Audit.actor_id == actor_id,
        Audit.action.in_(['skill.install', 'skill.update'])).order_by(Audit.created_at.desc()))
    return next((row for row in rows if row.after.get('transferId') == transfer_id), None)


def transfer_status(store, session, state):
    if state['status'] != 'installed':
        prior = committed_transfer(session, UUID(state['actor']), state['id'])
        if prior:
            state.update(status='installed', release=prior.after['release'], error=None)
            store.save(state)
    return state


def switch(store, session, actor, action, name, before, after, release, cleanup_plan=None):
    identifier = uuid4()
    root = store.installed_root
    previous, _ = catalog.read_catalog(root, store.protected)
    audit = Audit(id=identifier, actor_id=actor.id, action=action, target=name, before=before, after=after)
    session.add(audit)
    session.flush()
    pending = dict(audit=str(identifier), before=previous, after=release, cleanup=cleanup_plan)
    atomic_json(root / '.pending.json', pending)
    try:
        atomic_json(root / 'current.json', {'release': release})
        session.commit()
    except BaseException:
        session.rollback()
        recover(store, session)
        raise
    finish(store, session, pending, audit)
    return audit.after


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
    jobs = references.locked(session, {state['package']['name']})
    preparation.guard(store, {state['package']['name']})
    release, items = catalog.read_catalog(store.installed_root, store.protected)
    if base_release != release or state['baseRelease'] != release:
        raise HTTPException(409, '安装目录已变化，请重新校验并确认差异')
    checked = store.validate(transfer_id, actor_id)
    name = checked['package']['name']
    baseline = preparation.begin(store, session, jobs, {name})
    references.preserve(session, jobs)
    before = next((item for item in items if item['name'] == name), None)
    item = dict(checked['package'], entries=checked['entries'], rootName=checked['rootName'])
    updated = [row for row in items if row['name'] != name] + [item]
    new_release = prepare_release(store, updated, checked)
    retained = {(entry['name'], entry['checksum']) for entry in updated} | references.active_keys(jobs)
    cleanup_plan = cleanup.plan(store, {name}, retained, baseline['beforeBytes'],
                                preparation.history_bytes(baseline), transfer_id)
    row = session.get(InstalledSkillAvailability, name)
    if before is None:
        if row is None:
            row = InstalledSkillAvailability(id=name)
            session.add(row)
        row.enabled, row.platforms = False, []
        row.version = (row.version or 0) + 1
    switch(store, session, actor, 'skill.install' if before is None else 'skill.update', name,
           {'release': release, 'checksum': before['checksum'] if before else None},
           {'release': new_release, 'checksum': item['checksum'], 'transferId': transfer_id}, new_release, cleanup_plan)
    checked.update(status='installed', release=new_release)
    return store.save(checked)


def delete(store, session, actor_id, skill_id, body):
    actor = authorize(session, actor_id)
    release, items = catalog.read_catalog(store.installed_root, store.protected)
    item = next((item for item in items if catalog.identity(item['name']) == str(skill_id)), None)
    if item is None:
        rows = session.scalars(select(Audit).where(Audit.actor_id == actor.id,
                               Audit.action == 'skill.delete').order_by(Audit.created_at.desc()))
        prior = next((row for row in rows if catalog.identity(row.target) == str(skill_id)
                      and row.before == body.model_dump()), None)
        if prior:
            return {'deleted': True, 'release': prior.after['release'],
                    'reclaimedBytes': prior.after.get('reclaimedBytes', 0)}
        raise HTTPException(404, 'Skill 不在当前安装目录中')
    jobs = references.locked(session, {item['name']}, deleting=True)
    preparation.guard(store, {item['name']})
    # Gate acquired: reject concurrent publication/availability changes.
    current, _ = catalog.read_catalog(store.installed_root, store.protected)
    if current != release:
        raise HTTPException(409, '安装目录已变化，请刷新后重新确认删除')
    row = session.get(InstalledSkillAvailability, item['name'], populate_existing=True)
    version = row.version if row else 1
    if body.release != release or body.checksum != item['checksum'] or body.version != version:
        raise HTTPException(409, 'Skill 内容、开关或平台已变化，请刷新后重新确认删除')
    baseline = preparation.begin(store, session, jobs, {item['name']})
    references.preserve(session, jobs)
    updated = [entry for entry in items if entry['name'] != item['name']]
    new_release = prepare_release(store, updated)
    cleanup_plan = cleanup.plan(store, {item['name']}, {(entry['name'], entry['checksum']) for entry in updated},
                                baseline['beforeBytes'], preparation.history_bytes(baseline))
    if row:
        row.enabled, row.platforms, row.version = False, [], version + 1
    result = switch(store, session, actor, 'skill.delete', item['name'],
           {'release': release, 'checksum': item['checksum'], 'version': version},
           {'release': new_release, 'deleted': True}, new_release, cleanup_plan)
    return {'deleted': True, 'release': new_release, 'reclaimedBytes': result['reclaimedBytes']}
