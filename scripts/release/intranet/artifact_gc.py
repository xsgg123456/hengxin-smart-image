"""Registered release artifacts only; caller holds the release lock and verifies live state."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time

import cleanup_refs

PENDING = 'artifact-gc-pending.json'
RECEIPT = 'intranet-artifact-cleanup.json'
DEPENDENCIES = {'.venv', 'venv', 'node_modules', 'site-packages', 'pyvenv.cfg'}


def boundary(u, store, value, kind):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts or str(path) != str(value):
        raise RuntimeError('Noncanonical artifact path')
    if kind == 'package':
        valid = path.parent == u.ROOT and path.name.endswith(('.tar.gz', '.tgz'))
    elif kind == 'transaction':
        valid = path.parent == store.root / 'intranet-transactions'
    elif kind == 'legacy':
        valid = path.parent == u.ROOT and path.name.startswith(('unify-', 'unified-backup-'))
    else:
        valid = False
    if not valid or path.name.startswith('.'):
        raise RuntimeError('Outside artifact boundary')
    u.safe(path.parent)
    return path


def digest(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise RuntimeError('Unsafe artifact file')
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
        after = os.fstat(stream.fileno())
        if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise RuntimeError('Artifact changed while hashing')
        if (path.lstat().st_dev, path.lstat().st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError('Artifact file replaced')
        return h.hexdigest()


def proof(u, store, path, kind):
    path = boundary(u, store, path, kind)
    u.safe(path)
    # ismount alone misses same-filesystem bind mounts.
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        mount = Path(re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), line.split()[4]))
        if mount == path or path in mount.parents:
            raise RuntimeError('Mounted artifact content')
    info = path.lstat()
    directory = stat.S_ISDIR(info.st_mode)
    if (kind == 'package' and not stat.S_ISREG(info.st_mode)) or (kind != 'package' and not directory):
        raise RuntimeError('Unexpected artifact type')
    files, dirs, stack = {}, [], [path]
    while stack:
        item = stack.pop()
        u.safe(item)
        entry = item.lstat()
        if entry.st_dev != info.st_dev or os.path.ismount(item):
            raise RuntimeError('Mounted artifact content')
        if item.name in DEPENDENCIES:
            raise RuntimeError('Dependency content retained')
        name = item.relative_to(path).as_posix()
        if stat.S_ISDIR(entry.st_mode):
            dirs.append(name)
            stack.extend(sorted(item.iterdir(), reverse=True))
        elif stat.S_ISREG(entry.st_mode) and entry.st_nlink == 1:
            files[name] = digest(item)
        else:
            raise RuntimeError('Linked or special artifact content')
    final = path.lstat()
    if (info.st_dev, info.st_ino) != (final.st_dev, final.st_ino):
        raise RuntimeError('Artifact identity changed')
    return {'path': str(path), 'kind': kind, 'identity': [info.st_dev, info.st_ino],
            'files': files, 'dirs': sorted(dirs)}


def validate(u, store, expected, partial=False):
    actual = proof(u, store, expected['path'], expected['kind'])
    if actual['identity'] != expected['identity']:
        raise RuntimeError('Artifact identity drift')
    if partial:
        matches = (set(actual['dirs']) <= set(expected['dirs'])
                   and all(expected['files'].get(k) == v for k, v in actual['files'].items()))
    else:
        matches = actual == expected
    if not matches:
        raise RuntimeError('Artifact content drift')


def allocated(paths):
    """Count actual allocated blocks once, even if candidates overlap."""
    seen, total, stack = set(), 0, list(paths)
    while stack:
        path = Path(stack.pop())
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        identity = (info.st_dev, info.st_ino)
        if identity in seen:
            continue
        seen.add(identity)
        total += info.st_blocks * 512
        if stat.S_ISDIR(info.st_mode):
            stack.extend(path.iterdir())
    return total


def read_pending(u, store):
    path = store.root / PENDING
    if not path.exists() and not path.is_symlink():
        return {}
    u.safe(path)
    if path.stat().st_mode & 0o077 or path.stat().st_nlink != 1:
        raise RuntimeError('Pending artifact proof is not private')
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise RuntimeError('Invalid pending artifact proofs')
    return data


def protected(path, paths):
    return any(path == p or path in p.parents or p in path.parents for p in map(Path, paths))


def remove(u, store, item, partial):
    path = boundary(u, store, item['path'], item['kind'])
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        u.safe(path.parent)
        parent = path.parent.stat()
        opened = os.fstat(fd)
        if (parent.st_dev, parent.st_ino) != (opened.st_dev, opened.st_ino):
            raise RuntimeError('Artifact parent replaced')
        validate(u, store, item, partial)
        if cleanup_refs.host(u, path.parent).get(str(path)):
            raise RuntimeError('Artifact acquired a live reference')
        current = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
        if [current.st_dev, current.st_ino] != item['identity']:
            raise RuntimeError('Artifact replaced before deletion')
        if item['kind'] == 'package':
            os.unlink(path.name, dir_fd=fd)
        else:
            if not shutil.rmtree.avoids_symlink_attacks:
                raise RuntimeError('Safe descriptor deletion unavailable')
            shutil.rmtree(path.name, dir_fd=fd)
        if path.exists() or path.is_symlink():
            raise RuntimeError('Artifact still exists after deletion')
    finally:
        os.close(fd)


def execute(u, store, registry, protected_sources, protected_paths, apply=False):
    report = dict(status='preview', candidates=[], kept={}, deleted=[], errors=[], time_ns=time.time_ns())
    try:
        pending = read_pending(u, store)
    except Exception as exc:
        report.update(status='warning', errors=[{'type': type(exc).__name__, 'reason': 'pending-proof-unreadable'}])
        return report
    measured = []
    for value, entry in sorted(registry.items()):
        try:
            item = entry['proof']
            if item['path'] != value:
                raise RuntimeError('Registry path mismatch')
            path = boundary(u, store, value, item['kind'])
            if not path.exists() and not path.is_symlink():
                if apply and value in pending:
                    del pending[value]
                    store.report(PENDING, pending)
                continue
            measured.append(path)
            if not entry.get('owners') or set(entry['owners']) & protected_sources:
                report['kept'][value] = ['retained-or-unpublished-source']
                continue
            if protected(path, protected_paths):
                report['kept'][value] = ['retained-transaction-or-path']
                continue
            if value in pending and pending[value] != item:
                raise RuntimeError('Pending proof differs from registry')
            validate(u, store, item, value in pending)
            reasons = cleanup_refs.host(u, path.parent).get(value)
            if reasons:
                report['kept'][value] = reasons
            else:
                report['candidates'].append(value)
        except Exception as exc:
            report['errors'].append({'path': value, 'type': type(exc).__name__})
    report['before_bytes'] = allocated(measured)
    if apply:
        store.report(RECEIPT, dict(report, status='cleaning'))
        for value in report['candidates']:
            try:
                item = registry[value]['proof']
                partial = value in pending
                validate(u, store, item, partial)
                # Durable original manifest survives partial deletion; no copied artifact.
                pending[value] = item
                store.report(PENDING, pending)
                remove(u, store, item, partial)
                report['deleted'].append(value)
                del pending[value]
                store.report(PENDING, pending)
            except Exception as exc:
                report['errors'].append({'path': value, 'type': type(exc).__name__})
    report['after_bytes'] = allocated(measured)
    report['released_bytes'] = report['before_bytes'] - report['after_bytes']
    report['status'] = 'warning' if report['errors'] else ('complete' if apply else 'preview')
    if apply:
        store.report(RECEIPT, report)
    return report
