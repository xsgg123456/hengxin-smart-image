"""Conservative LAN source retention; caller holds the shared release lock."""
import json
import os
from pathlib import Path
import shutil
import stat
import time

import cleanup_refs
import cleanup_history
import cleanup_pending
import snapshot


def tree_size(path):
    """Allocated bytes, without following links; fail on unreadable entries."""
    total = 0
    stack = [path]
    while stack:
        item = stack.pop()
        info = item.lstat()
        total += getattr(info, 'st_blocks', (info.st_size + 511) // 512) * 512
        if stat.S_ISDIR(info.st_mode):
            stack.extend(item.iterdir())
    return total


def eligible(u, path):
    """Only plain, complete source releases. Dependencies/unknown contents stay."""
    if path.parent != snapshot.RELEASES or path.name.startswith('.'):
        raise RuntimeError('Outside release boundary')
    u.safe(path)
    if not path.is_dir():
        raise RuntimeError('Not a release directory')
    top = {p.name for p in path.iterdir()}
    required = {'backend', 'frontend', 'release-manifest.json'}
    if not required <= top or top - required - {'compatibility-files.json'}:
        raise RuntimeError('Unknown release contents')
    cleanup_pending.inventory(u, path)
    manifest = snapshot.manifest(u, path)
    legacy = path / 'compatibility-files.json'
    if legacy.exists():
        u.safe(legacy)
        compatibility = json.loads(legacy.read_bytes())
        if not isinstance(compatibility, dict) or any(
                not n.startswith('frontend/assets/') or manifest['files'].get(n) != h
                for n, h in compatibility.items()):
            raise RuntimeError('Unknown legacy compatibility manifest')
    info = path.stat()
    return (info.st_dev, info.st_ino)


def plan(u, store, data):
    if data.get('pending'):
        raise RuntimeError('Pending release blocks cleanup')
    root = snapshot.RELEASES
    u.safe(root)
    references = cleanup_refs.collect(u, data, root)
    history = cleanup_history.known(u, store, data)
    pending = cleanup_pending.read(u, store)
    kept, candidates = {}, []
    for path in sorted(root.iterdir()):
        if str(path) in references:
            kept[str(path)] = references[str(path)]
            continue
        if pending and Path(pending['path']).exists():
            if str(path) != pending['path']:
                kept[str(path)] = ['waiting-for-partial-cleanup']
                continue
            identity = cleanup_pending.check(u, pending)
            candidates.append({'path': str(path), 'identity': identity, 'bytes': tree_size(path)})
            continue
        if str(path) not in history:
            kept[str(path)] = ['unpublished-or-unknown-source']
            continue
        try:
            identity = eligible(u, path)
        except (RuntimeError, OSError, ValueError, KeyError):
            kept[str(path)] = ['unrecognized-or-unsafe-release']
            continue
        candidates.append({'path': str(path), 'identity': identity, 'bytes': tree_size(path)})
    return {'kept': kept, 'candidates': candidates}


def execute(u, store, data, apply=False):
    # A failed postcheck must prevent *all* deletion, including manual retries.
    if data.get('pending'):
        raise RuntimeError('Pending release blocks cleanup')
    snapshot.same(data['current'], snapshot.capture(u, runtime=True))
    report = dict(plan(u, store, data), status='preview', deleted=[], errors=[], time_ns=time.time_ns())
    if not apply:
        return report
    if not shutil.rmtree.avoids_symlink_attacks:
        raise RuntimeError('Safe directory-descriptor deletion is unavailable')
    root = snapshot.RELEASES
    report['before_bytes'] = tree_size(root)
    report['state_before_bytes'] = tree_size(store.root)
    # Persist the plan before deleting; no additional copy of old releases is made.
    report['status'] = 'cleaning'
    store.report('intranet-cleanup.json', report)
    pending = cleanup_pending.read(u, store)
    if pending and not Path(pending['path']).exists():
        cleanup_pending.forget(u, store)
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for item in report['candidates']:
            path = Path(item['path'])
            try:
                u.safe(root)
                info = root.stat()
                opened = os.fstat(root_fd)
                if (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
                    raise RuntimeError('Release root replaced')
                reasons = cleanup_refs.collect(u, data, root).get(str(path))
                if reasons:
                    report['kept'][str(path)] = reasons
                    continue
                proof = cleanup_pending.read(u, store)
                if proof and proof['path'] != str(path):
                    raise RuntimeError('Another partial cleanup requires recovery')
                identity = cleanup_pending.check(u, proof) if proof else eligible(u, path)
                if identity != tuple(item['identity']):
                    raise RuntimeError('Release identity changed')
                if proof is None:
                    proof = cleanup_pending.inventory(u, path)
                    store.report(cleanup_pending.NAME, proof)
                shutil.rmtree(path.name, dir_fd=root_fd)
                if path.exists():
                    raise RuntimeError('Release still exists after deletion')
                report['deleted'].append(str(path))
                cleanup_pending.forget(u, store)
                store.report('intranet-cleanup.json', report)
            except Exception as exc:
                report['errors'].append({'path': str(path), 'type': type(exc).__name__})
                break  # Unknown state: stop, keep the successful application release.
    finally:
        os.close(root_fd)
    report['after_bytes'] = tree_size(root)
    report['released_bytes'] = report['before_bytes'] - report['after_bytes']
    report['status'] = 'warning' if report['errors'] else 'complete'
    # Reserve fields before measuring the receipt itself, then account for its blocks.
    report.update(state_growth_bytes=0, net_released_bytes=0)
    for _ in range(3):
        store.report('intranet-cleanup.json', report)
        growth = tree_size(store.root) - report['state_before_bytes']
        report.update(state_growth_bytes=growth, net_released_bytes=report['released_bytes'] - growth)
    store.report('intranet-cleanup.json', report)
    return report
