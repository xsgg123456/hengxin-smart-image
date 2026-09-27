"""Whitelisted delivery release, including an offline virtualenv rollback."""
import hashlib
import json
import os
import posixpath
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile

FILES = tuple('app/execution/' + name + '.py' for name in (
    'codex_runner', 'delivery_acceptance', 'delivery_markdown', 'delivery_snapshot',
    'delivery_state', 'delivery_storage', 'events', 'final_delivery',
    'intervention', 'observation',
)) + ('app/modules/tasks/observations.py', 'app/modules/tasks/queries.py',
     'app/worker/reconcile.py', 'app/worker/repair_delivery.py', 'pyproject.toml', 'uv.lock')


def clean(path):
    path = Path(os.path.abspath(path))
    if any(p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction())
           for p in (path, *path.parents)):
        raise ValueError('Symlink or junction in managed path')
    return path


def safe_path(root, name):
    if name not in FILES:
        raise ValueError('File outside release whitelist')
    return clean(root / name)


def roots(native, backup=None):
    native = clean(native)
    if not native.is_dir() or {'runtime', 'auth', '.venv'} & set(native.parts):
        raise ValueError('Unsafe native directory')
    if not safe_path(native, FILES[0]).is_file():
        raise ValueError('Missing native codex_runner reference')
    if backup is not None:
        backup = clean(backup)
        if (not backup.is_dir() or backup.is_relative_to(native)
                or native.is_relative_to(backup) or native.stat().st_dev != backup.stat().st_dev):
            raise ValueError('Backup and native directories must be separate')
    return native, backup


def metadata(path):
    value = path.stat()
    return dict(mode=value.st_mode & 0o777, uid=value.st_uid, gid=value.st_gid)


def apply_metadata(path, value):
    if hasattr(os, 'chown'):
        os.chown(path, value['uid'], value['gid'])
    os.chmod(path, value['mode'])


def replace(source, dest, attrs):
    temporary = clean(dest.with_suffix(dest.suffix + '.release-new'))
    if temporary.exists():
        raise ValueError('Unexpected native temporary file')
    try:
        with temporary.open('xb') as output, source.open('rb') as stream:
            shutil.copyfileobj(stream, output)
        apply_metadata(temporary, attrs)
        os.replace(temporary, dest)
    finally:
        temporary.unlink(missing_ok=True)


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def validate_members(members):
    names = set()
    links = set()
    for member in members:
        path = PurePosixPath(member.name)
        if (path.is_absolute() or '..' in path.parts or '\\' in member.name
                or member.name != path.as_posix()
                or not path.parts or path.parts[0] != '.venv' or ':' in member.name
                or member.name in names or not (member.isfile() or member.isdir() or member.issym())):
            raise ValueError('Unsafe virtualenv archive member')
        names.add(member.name)
        if member.issym():
            links.add(path)
            target = member.linkname
            resolved = posixpath.normpath('/' + str(path.parent / target))
            internal = resolved == '/.venv' or resolved.startswith('/.venv/')
            python_link = (path.parent == PurePosixPath('.venv/bin')
                           and re.fullmatch(r'python[0-9.]*', path.name)
                           and target.startswith('/')
                           and re.fullmatch(r'python[0-9.]*', PurePosixPath(target).name))
            if '\\' in target or not (internal or python_link):
                raise ValueError('Unsafe virtualenv symlink')
    if any(any(parent in links for parent in PurePosixPath(name).parents) for name in names):
        raise ValueError('Archive writes through symlink')
    root = next((member for member in members if member.name == '.venv'), None)
    if root is None or not root.isdir():
        raise ValueError('Missing virtualenv root directory')


def backup_files(native, backup):
    native, backup = roots(native, backup)
    saved = clean(backup / 'native-files')
    saved.mkdir()
    state = {'files': {}, 'venv': False}
    for name in FILES:
        path = safe_path(native, name)
        state['files'][name] = metadata(path) if path.exists() else None
        if path.exists():
            if not path.is_file():
                raise ValueError('Native source must be a regular file')
            dest = safe_path(saved, name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
    venv = clean(native / '.venv')
    if venv.exists():
        if not venv.is_dir():
            raise ValueError('Virtualenv must be a directory')
        archive = clean(backup / 'native-venv.tar')
        with tarfile.open(archive, 'x', dereference=False) as tar:
            def independent_member(member):
                tar.inodes.clear()  # uv hardlinks become independent regular files.
                return member
            tar.add(venv, arcname='.venv', filter=independent_member)
        with tarfile.open(archive) as tar:
            validate_members(tar.getmembers())
        state.update(venv=True, venv_sha256=digest(archive))
    with clean(backup / 'native-state.json').open('x', encoding='utf-8') as stream:
        json.dump(state, stream)


def install_files(source, native):
    native, _ = roots(native)
    source = clean(source / 'backend')
    pairs = [(safe_path(source, n), safe_path(native, n)) for n in FILES]
    if any(not src.is_file() for src, _ in pairs):
        raise FileNotFoundError('Release source is incomplete')
    reference = metadata(safe_path(native, FILES[0]))
    for src, dest in pairs:
        if not dest.parent.is_dir():
            raise ValueError('Missing native module directory')
        replace(src, dest, metadata(dest) if dest.exists() else reference)


def stage_venv(backup, state):
    if not state['venv']:
        return None
    archive = clean(backup / 'native-venv.tar')
    if digest(archive) != state.get('venv_sha256'):
        raise ValueError('Virtualenv backup checksum mismatch')
    staged = clean(backup / 'restored-venv')
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        validate_members(members)
        staged.mkdir()
        for member in sorted(members, key=lambda item: (item.issym(), len(PurePosixPath(item.name).parts))):
            dest = staged / member.name
            if member.isdir():
                dest.mkdir(exist_ok=True)
            elif member.issym():
                os.symlink(member.linkname, dest)
                if hasattr(os, 'lchown'):
                    os.lchown(dest, member.uid, member.gid)
            else:
                with tar.extractfile(member) as src, dest.open('xb') as output:
                    shutil.copyfileobj(src, output)
        for member in reversed(members):
            if not member.issym():
                dest = staged / member.name
                apply_metadata(dest, dict(mode=member.mode, uid=member.uid, gid=member.gid))
                os.utime(dest, (member.mtime, member.mtime))
    return staged / '.venv'


def restore_files(native, backup):
    native, backup = roots(native, backup)
    state = json.loads(clean(backup / 'native-state.json').read_text(encoding='utf-8'))
    existing = state.get('files', {})
    if set(existing) != set(FILES) or type(state.get('venv')) is not bool:
        raise ValueError('Invalid native backup state')
    for name, attrs in existing.items():
        safe_path(native, name)
        if attrs is not None:
            if (not isinstance(attrs, dict) or set(attrs) != {'mode', 'uid', 'gid'}
                    or any(type(v) is not int or v < 0 for v in attrs.values())
                    or attrs['mode'] > 0o777):
                raise ValueError('Invalid native file metadata')
            if not safe_path(backup / 'native-files', name).is_file():
                raise ValueError('Incomplete native source backup')
    venv, failed = clean(native / '.venv'), clean(backup / 'failed-venv')
    if failed.exists():
        raise ValueError('Previous failed virtualenv already preserved')
    staged = stage_venv(backup, state)
    for name, attrs in existing.items():
        dest = safe_path(native, name)
        if attrs is None:
            dest.unlink(missing_ok=True)
        else:
            replace(safe_path(backup / 'native-files', name), dest, attrs)
    if venv.exists():
        os.rename(venv, failed)
    if staged is not None:
        os.rename(staged, venv)


if __name__ == '__main__':
    mode, first, second = sys.argv[1:]
    {'backup': backup_files, 'install': install_files, 'restore': restore_files}[mode](Path(first), Path(second))
