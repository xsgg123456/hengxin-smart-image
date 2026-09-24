"""Strict native-worker file set, reversible even when new modules did not exist."""
import json
import os
from pathlib import Path
import shutil
import sys

FILES = tuple('app/execution/' + name + '.py' for name in (
    'codex_runner', 'materials', 'material_backfill', 'material_bindings',
    'material_capture', 'material_history', 'material_literals',
))


def safe_path(root, name):
    if name not in FILES:
        raise ValueError('Native file outside release whitelist')
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Unsafe native path')
    return path


def backup_files(native, backup):
    saved = backup / 'native-files'
    saved.mkdir()
    existing = {}
    for name in FILES:
        path = safe_path(native, name)
        existing[name] = path.exists()
        if path.exists():
            dest = safe_path(saved, name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            if hasattr(os, 'chown'):
                stat = path.stat()
                os.chown(dest, stat.st_uid, stat.st_gid)
    (backup / 'native-state.json').write_text(json.dumps(existing), encoding='utf-8')


def replace(source, dest, reference):
    stat = reference.stat()
    temporary = dest.with_suffix('.release-new')
    if temporary.exists() or temporary.is_symlink():
        raise ValueError('Unexpected native temporary file')
    try:
        shutil.copy2(source, temporary)
        if hasattr(os, 'chown'):
            os.chown(temporary, stat.st_uid, stat.st_gid)
        os.chmod(temporary, stat.st_mode & 0o777)
        os.replace(temporary, dest)
    finally:
        temporary.unlink(missing_ok=True)


def install_files(source, native):
    for name in FILES:
        dest = safe_path(native, name)
        original = dest if dest.exists() else safe_path(native, FILES[0])
        replace(safe_path(source / 'backend', name), dest, original)


def restore_files(native, backup):
    existing = json.loads((backup / 'native-state.json').read_text(encoding='utf-8'))
    if set(existing) != set(FILES) or any(type(value) is not bool for value in existing.values()):
        raise ValueError('Native backup state does not match release whitelist')
    for name in FILES:
        dest = safe_path(native, name)
        if existing[name]:
            saved = safe_path(backup / 'native-files', name)
            replace(saved, dest, saved)
        else:
            dest.unlink(missing_ok=True)


if __name__ == '__main__':
    mode, first, second = sys.argv[1:]
    {'backup': backup_files, 'install': install_files, 'restore': restore_files}[mode](Path(first), Path(second))
