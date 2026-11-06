"""Durable original accounting window before any private or central copy."""
import json
import os
from uuid import UUID

from fastapi import HTTPException

from app.overseas.execution import skill_history
from app.overseas.studio import context_fs as fs
from . import installed_catalog as catalog, skill_cleanup as cleanup, skill_references as references
from .installed_tree import NAME, digest, read_file, safe_directory
from .skill_transfer_store import atomic_json, sync_directory


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError('Invalid preparation accounting size')


def owner_parts(value):
    if not isinstance(value, str):
        raise ValueError('Invalid preparation owner')
    parts = value.split('/')
    if not (len(parts) == 1 or len(parts) == 2 and parts[0] == 'studio'):
        raise ValueError('Invalid preparation owner')
    if str(UUID(parts[-1])) != parts[-1]:
        raise ValueError('Invalid preparation owner identity')
    return parts


def load(root, protected=False):
    safe_directory(root, protected=protected)
    path = root / '.preparing.json'
    if not os.path.lexists(path):
        return None
    value = json.loads(read_file(path, protected=protected))
    if (not isinstance(value, dict) or set(value) != {
            'schema', 'names', 'beforeBytes', 'owners', 'metadata', 'digest'}
            or type(value['schema']) is not int or value['schema'] != 1):
        raise ValueError('Invalid preparation journal')
    payload = {key: item for key, item in value.items() if key != 'digest'}
    if digest(payload) != value['digest']:
        raise ValueError('Preparation journal integrity mismatch')
    names = value['names']
    if (not isinstance(names, list) or any(
            not isinstance(name, str) or not NAME.fullmatch(name) for name in names)
            or names != sorted(set(names))):
        raise ValueError('Invalid preparation Skill scope')
    integer(value['beforeBytes'])
    if not isinstance(value['owners'], dict) or not isinstance(value['metadata'], dict):
        raise ValueError('Invalid preparation baselines')
    allowed = set()
    for owner, size in value['owners'].items():
        parts = owner_parts(owner)
        integer(size)
        allowed.update(('', owner, owner + '/.context-prepare.lock'))
        if len(parts) == 2:
            allowed.add('studio')
    if set(value['metadata']) != allowed:
        raise ValueError('Invalid preparation metadata scope')
    for size in value['metadata'].values():
        integer(size)
    return value


def guard(store, names):
    value = load(store.installed_root, store.protected)
    if value and not set(value['names']) <= set(names):
        raise HTTPException(409, '存在未完成的 Skill 准备，请先重试原技能：' + ', '.join(value['names']))
    return value


def metadata_size(path, directory):
    path = fs.checked(path, missing=True, directory=directory)
    if not os.path.lexists(path):
        return 0
    info = path.lstat()
    return info.st_blocks * 512 if os.name == 'posix' else (0 if directory else info.st_size)


def save(store, value):
    path = store.installed_root / '.preparing.json'
    safe_directory(store.installed_root, protected=store.protected)
    if os.path.lexists(path):
        read_file(path, protected=store.protected)
    value['digest'] = digest({key: item for key, item in value.items() if key != 'digest'})
    atomic_json(path, value)


def begin(store, session, jobs, names):
    value = guard(store, names)
    owners = references.owners(session, jobs)
    # Validate existing exact snapshots before creating durable state; no copies yet.
    for _, owner, skill in owners:
        _, item, _ = catalog.frozen_item(skill)
        if owner.exists():
            skill_history.find(owner, item)
    if value is None:
        value = dict(schema=1, names=sorted(names), beforeBytes=cleanup.footprint(store), owners={}, metadata={})
    else:
        value['names'] = sorted(set(value['names']) | set(names))
    if owners or value['owners']:
        root = references.execution_root()
        for base, owner, _ in owners:
            relative = owner.relative_to(root).as_posix()
            parts = owner_parts(relative)
            if base != (root / 'studio' if len(parts) == 2 else root):
                raise ValueError('Preparation owner has wrong base')
            fs.checked(owner, missing=True, directory=True)
            if relative not in value['owners']:
                value['owners'][relative] = cleanup.allocated(owner / 'skill-history')
            for path in (root, base, owner, owner / '.context-prepare.lock'):
                key = path.relative_to(root).as_posix()
                key = '' if key == '.' else key
                if key not in value['metadata']:
                    value['metadata'][key] = metadata_size(path, path.name != '.context-prepare.lock')
        # Replay every original path before allowing new preservation.
        history_bytes(value)
    save(store, value)
    return value


def history_bytes(value):
    if not value['owners']:
        return 0
    root = references.execution_root()
    added = 0
    for relative, before in value['owners'].items():
        owner = fs.checked(root.joinpath(*owner_parts(relative)), missing=True, directory=True)
        added += max(0, cleanup.allocated(owner / 'skill-history') - before)
    for relative, before in value['metadata'].items():
        path = root / relative if relative else root
        added += max(0, metadata_size(path, path.name != '.context-prepare.lock') - before)
    return added


def clear(store):
    path = store.installed_root / '.preparing.json'
    if load(store.installed_root, store.protected) is not None:
        path.unlink()
        sync_directory(store.installed_root)
