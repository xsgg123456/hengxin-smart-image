"""Root-only immutable publication, DB admission ordering and crash recovery."""
import json
import os
import shutil
import tempfile
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.auth.models import Member
from app.overseas.execution.queue import lock_gate
from app.overseas.tasks.service import lock_actor
from . import installed_catalog as catalog
from .installed_tree import digest, tree
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
    root = store.installed_root
    old_release, _ = catalog.read_catalog(root, store.protected)
    releases = root / 'releases'
    releases.mkdir(exist_ok=True, mode=0o755)
    if old_release is None:
        # A failed first copy must still leave an indexed, readable empty installation.
        empty = {'schema': 1, 'items': []}
        empty_release = digest(empty)
        empty_folder = releases / empty_release
        empty_folder.mkdir(exist_ok=True, mode=0o755)
        atomic_json(empty_folder / 'manifest.json', empty)
        atomic_json(root / 'current.json', {'release': empty_release})
    staging = type(root)(tempfile.mkdtemp(prefix='.install-', dir=releases))
    try:
        for item in items:
            if replacement and item['name'] == replacement['package']['name']:
                source = store.directory(replacement['id']) / 'package'
            else:
                source = releases / old_release / item['name']
            package, entries = tree(source)
            if package.checksum != item['checksum'] or entries != item['entries']:
                raise ValueError('发布源文件与清单不符')
            destination = staging / item['name']
            destination.mkdir(mode=0o755)
            for relative, info in entries.items():
                path = destination / relative
                if info.get('directory'):
                    path.mkdir(parents=True, exist_ok=True, mode=0o755)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                    with path.open('wb') as output:
                        output.write(package.files[relative])
                        output.flush()
                        os.fsync(output.fileno())
                    path.chmod(0o755 if path.suffix.lower() in ('.sh', '.py') else 0o644)
            catalog.verify_package(staging, item, store.protected)
        manifest = dict(schema=1, items=sorted(items, key=lambda row: row['name']))
        release = digest(manifest)
        atomic_json(staging / 'manifest.json', manifest)
        staging.chmod(0o755)
        for path in staging.rglob('*'):
            if path.is_dir():
                path.chmod(0o755)
                sync_directory(path)
        sync_directory(staging)
        target = releases / release
        if not target.exists():
            staging.rename(target)
            sync_directory(releases)
        directory, verified = catalog.release_manifest(root, release, store.protected)
        for item in verified['items']:
            catalog.verify_package(directory, item, store.protected)
        return release
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def recover(store, session):
    """Caller holds the publisher lock; DB gate excludes new round admission."""
    journal = store.installed_root / '.pending.json'
    if not journal.exists():
        return
    lock_gate(session)
    pending = json.loads(journal.read_text(encoding='utf-8'))
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
    journal.unlink()
    sync_directory(store.installed_root)
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


def switch(store, session, actor, action, name, before, after, release):
    identifier = uuid4()
    root = store.installed_root
    previous, _ = catalog.read_catalog(root, store.protected)
    session.add(Audit(id=identifier, actor_id=actor.id, action=action, target=name,
                      before=before, after=after))
    session.flush()
    atomic_json(root / '.pending.json', dict(audit=str(identifier), before=previous, after=release))
    try:
        atomic_json(root / 'current.json', {'release': release})
        session.commit()
    except BaseException:
        session.rollback()
        recover(store, session)
        raise
    (root / '.pending.json').unlink()
    sync_directory(root)


def install(store, session, actor_id, transfer_id, base_release):
    actor = authorize(session, actor_id)
    lock_gate(session)
    state = store.load(transfer_id, actor_id)
    if state['status'] == 'installed':
        return state
    prior = committed_transfer(session, actor.id, transfer_id)
    if prior:
        state.update(status='installed', release=prior.after['release'], error=None)
        return store.save(state)
    if state['status'] not in ('validated', 'failed') or not state.get('package'):
        raise HTTPException(409, '请先完成服务端校验')
    release, items = catalog.read_catalog(store.installed_root, store.protected)
    if base_release != release or state['baseRelease'] != release:
        raise HTTPException(409, '安装目录已变化，请重新校验并确认差异')
    checked = store.validate(transfer_id, actor_id)
    name = checked['package']['name']
    if checked['change'] == 'identical':
        checked.update(status='installed', release=release)
        return store.save(checked)
    before = next((item for item in items if item['name'] == name), None)
    item = dict(checked['package'], entries=checked['entries'], rootName=checked['rootName'])
    updated = [row for row in items if row['name'] != name] + [item]
    new_release = prepare_release(store, updated, checked)
    row = session.get(InstalledSkillAvailability, name)
    if before is None:
        if row is None:
            row = InstalledSkillAvailability(id=name)
            session.add(row)
        row.enabled, row.platforms = False, []
        row.version = (row.version or 0) + 1
    switch(store, session, actor, 'skill.install' if before is None else 'skill.update', name,
           {'release': release, 'checksum': before['checksum'] if before else None},
           {'release': new_release, 'checksum': item['checksum'], 'transferId': transfer_id}, new_release)
    checked.update(status='installed', release=new_release)
    return store.save(checked)


def delete(store, session, actor_id, skill_id, body):
    actor = authorize(session, actor_id)
    lock_gate(session)
    release, items = catalog.read_catalog(store.installed_root, store.protected)
    item = next((item for item in items if catalog.identity(item['name']) == str(skill_id)), None)
    if item is None:
        rows = session.scalars(select(Audit).where(Audit.actor_id == actor.id,
                               Audit.action == 'skill.delete').order_by(Audit.created_at.desc()))
        prior = next((row for row in rows if catalog.identity(row.target) == str(skill_id)
                      and row.before == body.model_dump()), None)
        if prior:
            return {'deleted': True, 'release': prior.after['release']}
        raise HTTPException(404, 'Skill 不在当前安装目录中')
    row = session.get(InstalledSkillAvailability, item['name'])
    version = row.version if row else 1
    if body.release != release or body.checksum != item['checksum'] or body.version != version:
        raise HTTPException(409, 'Skill 内容、开关或平台已变化，请刷新后重新确认删除')
    updated = [entry for entry in items if entry['name'] != item['name']]
    new_release = prepare_release(store, updated)
    if row:
        row.enabled, row.platforms, row.version = False, [], version + 1
    switch(store, session, actor, 'skill.delete', item['name'],
           {'release': release, 'checksum': item['checksum'], 'version': version},
           {'release': new_release, 'deleted': True}, new_release)
    return {'deleted': True, 'release': new_release}
