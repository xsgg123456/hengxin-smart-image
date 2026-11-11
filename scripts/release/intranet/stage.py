"""Unpack a trusted package into a new immutable LAN candidate directory."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import tarfile

import engine
import cleanup_history
import catalog
import artifact_gc
from release import Release, retention_store
from snapshot import RELEASES, sha


def unpack(archive, name, u, used=()):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}', name):
        raise RuntimeError('Invalid release name')
    root = RELEASES / name
    if str(root) in used:
        raise RuntimeError('Release name was already used; choose a new immutable name')
    u.safe(RELEASES)
    if root.exists():
        raise RuntimeError('Candidate directory already exists')
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        if len(set(names)) != len(names) or len(names) > 30000 or sum(m.size for m in members) > 2 * 1024**3:
            raise RuntimeError('Duplicate or oversized package')
        for item in members:
            p = PurePosixPath(item.name)
            if not item.isfile() or str(p) != item.name or p.is_absolute() or '..' in p.parts or '\\' in item.name:
                raise RuntimeError('Package contains unsafe member')
            if item.name != 'release-manifest.json' and p.parts[0] not in ('backend', 'frontend'):
                raise RuntimeError('Unexpected package member')
        manifest = json.loads(tar.extractfile('release-manifest.json').read())
        if set(names) != set(manifest['files']) | {'release-manifest.json'}:
            raise RuntimeError('Package inventory mismatch')
        # Validate everything before creating a candidate. Never extract tar ownership/links.
        for item in members:
            if item.name != 'release-manifest.json' and sha(tar.extractfile(item).read()) != manifest['files'][item.name]:
                raise RuntimeError('Package checksum mismatch')
        root.mkdir(mode=0o755)
        for item in members:
            target = root / item.name
            target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            u.safe(target, missing=True)
            mode = 0o755 if item.name == 'backend/app/execution/office_render.py' else 0o644
            u.write(target, tar.extractfile(item).read(), mode=mode, exclusive=True)
    old = u.RELEASE
    try:
        u.RELEASE = root
        u.validate_release()
    finally:
        u.RELEASE = old
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('Only root on hengxin-ai-245 is supported')
    store = retention_store(Path('/var/lib/hengxin-release'))
    engine.u.safe(store.root)
    with store.locked():
        tool = Release(store)
        marker = store.root/'intranet-split-migration.json'
        if marker.exists():
            engine.u.safe(marker)
            if json.loads(marker.read_bytes())['phase'] not in ('complete', 'rolled-back'):
                raise RuntimeError('Resolve split migration before staging')
        data = catalog.before(engine.u, store, tool.load())
        if data.get('pending') or data.get('migration_pending'):
            raise RuntimeError('Pending deployment blocks staging')
        history = cleanup_history.known(engine.u, store, data)
        # Uploads are immutable and version-named; never overwrite a registered tar.
        if str(args.archive) in data['retention']['artifacts']:
            raise RuntimeError('Archive path already registered; use a new version-specific filename')
        proof = artifact_gc.proof(engine.u, store, args.archive, 'package')
        root = unpack(args.archive, args.name, engine.u, used=history)
        artifact_gc.validate(engine.u, store, proof)
        catalog.stage(engine.u, store, data, root, args.archive)
        tool.save(data)
        print(root)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('LAN_STAGE_REFUSED: ' + (str(exc) if isinstance(exc, RuntimeError)
                                               else type(exc).__name__)) from None
