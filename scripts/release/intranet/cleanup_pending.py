"""Private deletion proof permits safe retries after partial directory removal."""
import json
import os
from pathlib import Path, PurePosixPath
import stat

import snapshot

NAME = 'intranet-cleanup-pending.json'


def inventory(u, path):
    u.safe(path)
    device = path.stat().st_dev
    files, directories = {}, []
    for folder, dirs, names in os.walk(path, followlinks=False):
        directory = Path(folder)
        u.safe(directory)
        directories.append(directory.relative_to(path).as_posix())
        for name in [*dirs, *names]:
            item = directory / name
            u.safe(item)
            info = item.lstat()
            if info.st_dev != device or os.path.ismount(item):
                raise RuntimeError('Mounted release content')
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise RuntimeError('Special release content')
            if name in ('.venv', 'venv', 'node_modules', 'site-packages', 'pyvenv.cfg'):
                raise RuntimeError('Dependency directory retained')
            if stat.S_ISREG(info.st_mode):
                files[item.relative_to(path).as_posix()] = snapshot.sha(item.read_bytes())
    info = path.stat()
    return {'path': str(path), 'identity': [info.st_dev, info.st_ino],
            'files': files, 'directories': directories}


def read(u, store):
    path = store.root / NAME
    if not path.exists():
        return None
    u.safe(path)
    proof = json.loads(path.read_bytes())
    snapshot.release_path(proof['path'])
    if not isinstance(proof['files'], dict) or not isinstance(proof['directories'], list):
        raise RuntimeError('Invalid pending cleanup proof')
    for name in [*proof['files'], *proof['directories']]:
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or str(rel) != name:
            raise RuntimeError('Invalid cleanup proof path')
    return proof


def check(u, proof):
    path = snapshot.release_path(proof['path'])
    actual = inventory(u, path)
    if (actual['identity'] != proof['identity']
            or not set(actual['directories']) <= set(proof['directories'])
            or any(proof['files'].get(n) != h for n, h in actual['files'].items())):
        raise RuntimeError('Partially removed release drift')
    return tuple(actual['identity'])


def forget(u, store):
    path = store.root / NAME
    u.safe(path)
    path.unlink()
