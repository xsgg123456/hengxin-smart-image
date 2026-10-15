"""Conversation-level Studio work, with DB-owned history supplied by the caller."""
import os
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from . import context_assets as assets
from . import context_fs as fs
from . import context_migration as migration


def _history(history):
    result, seen = [], set()
    for turn in history:
        identity = str(UUID(str(turn['turn_id'])))
        if identity in seen or not isinstance(turn['inputs'], list):
            raise ValueError('Invalid context history')
        seen.add(identity)
        result.append(dict(turn_id=identity, inputs=[assets.source(value) for value in turn['inputs']]))
    return result


def _root(workspace):
    home = fs.checked(Path(workspace.home), directory=True)
    root = fs.checked(home.parent, directory=True)
    if home.name != 'home' or str(UUID(root.name)) != root.name:
        raise ValueError('Invalid conversation context root')
    round_work = fs.checked(Path(getattr(workspace, 'round_work', workspace.work)),
                            missing=True, directory=True)
    if round_work.parent != root / 'rounds' or str(UUID(round_work.name)) != round_work.name:
        raise ValueError('Round workspace does not belong to the conversation')
    fs.checked(round_work, missing=True, directory=True)
    return root, round_work


def _empty(root):
    return dict(version=1, conversation_id=root.name, assets={}, aliases={}, files=[], managed_turns=[])


def _load(persistent, root):
    manifest = fs.load(persistent / 'manifest.json')
    if (manifest.get('version') != 1 or manifest.get('conversation_id') != root.name
            or any(not isinstance(manifest.get(field), kind) for field, kind in
                   [('assets', dict), ('aliases', dict), ('files', list), ('managed_turns', list)])):
        raise ValueError('Invalid persistent context marker')
    for turn in manifest['managed_turns']:
        if str(UUID(turn)) != turn:
            raise ValueError('Invalid managed context turn')
    notice = manifest.get('recovery_notice_turns')
    if notice is not None and (not isinstance(notice, list) or
            any(not isinstance(turn, str) or str(UUID(turn)) != turn for turn in notice)):
        raise ValueError('Invalid maintenance recovery notice')
    for item in manifest['files']:
        for name in ('relative', 'logical', 'path'):
            fs.relative(item[name])
        if item['turn_id'] != 'workspace' and str(UUID(item['turn_id'])) != item['turn_id']:
            raise ValueError('Invalid context file origin')
    return manifest


def _slots(work):
    fs.mkdir(work)
    for name in ('inputs', 'skills'):
        fs.mkdir(work / name)
    for name in ('input.json', '.context-files.json'):
        path = fs.checked(work / name, missing=True, directory=False)
        if not os.path.lexists(path):
            fs.write(path, b'{}')


def inspect(workspace, history):
    """No lock, directory creation or downloads; suitable for an operator dry run."""
    root, _ = _root(workspace)
    history = _history(history)
    return migration.inventory(history, migration.scan(root, history, include_originals=True))


def prepare(workspace, history, current_inputs, read_source):
    """The caller must establish DB ownership and exclude a running CLI first."""
    root, round_work = _root(workspace)
    history = _history(history)
    current_inputs = [assets.source(value) for value in current_inputs]
    persistent = root / 'persistent'
    with fs.lock(root):
        fs.checked(persistent, missing=True, directory=True)
        existing = persistent.exists()
        manifest = _load(persistent, root) if existing else _empty(root)
        notice = manifest.get('recovery_notice_turns')
        pending_notice = notice is not None and all(turn['turn_id'] in notice for turn in history)
        previous_assets = set(manifest['assets'])
        candidates, paths = assets.register(manifest, history, current_inputs, round_work.name, root)
        scanned = migration.scan(root, history, manifest['managed_turns'])
        temporary = root / ('.context-stage-' + uuid4().hex) if not existing else None
        target = persistent if existing else temporary
        try:
            fs.space(root, sum(item['size_bytes'] for item in scanned) if not existing else 0)
            fs.mkdir(target)
            _slots(target / 'work')
            restored = assets.restore(target, manifest, candidates, read_source,
                reserve=sum(item['size_bytes'] for item in scanned) if not existing else 0)
            interrupted = os.path.lexists(target / migration.JOURNAL)
            migrated = migration.apply(target, root, manifest, scanned)
            changed = bool(interrupted or migrated or restored & previous_assets
                           or (not existing and candidates))
            if changed or getattr(workspace, 'maintenance_recovery', False):
                manifest['recovery_notice_turns'] = [turn['turn_id'] for turn in history]
            if (round_work.name not in manifest['managed_turns']
                    and round_work.name not in {turn['turn_id'] for turn in history}):
                manifest['managed_turns'].append(round_work.name)
            manifest['source_digest'] = migration.inventory(history, scanned)['digest']
            index = dict(version=1, inputs=assets.public(manifest), files=migration.public(manifest))
            fs.save(target / 'context-index.json', index)
            # This private commit marker is never mounted into the model's work.
            fs.save(target / 'manifest.json', manifest)
            journal = target / migration.JOURNAL
            if os.path.lexists(journal):
                fs.checked(journal, directory=False).unlink()
            fs.sync(target)
            if temporary is not None:
                os.rename(temporary, persistent)
                fs.sync(root)
        except Exception:
            if temporary is not None and temporary.exists():
                if temporary.parent != root or not temporary.name.startswith('.context-stage-'):
                    raise ValueError('Invalid context staging cleanup target')
                fs.checked(temporary, directory=True)
                shutil.rmtree(temporary)
            raise
        workspace.round_work = round_work
        workspace.work = persistent / 'work'
        workspace.inputs_root = persistent / 'inputs'
        workspace.context_index = persistent / 'context-index.json'
        workspace.recovery_notice = pending_notice or changed
        workspace.persistent = True
        return paths
