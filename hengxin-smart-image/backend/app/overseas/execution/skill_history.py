"""Read verified Skill bytes only from the owning conversation/job's history."""
import hashlib
import os
import stat
from pathlib import Path
from uuid import UUID, uuid4

from app.overseas.management.installed_tree import read_file, safe_directory
from app.overseas.studio import context_fs as fs


def owner(workspace):
    home = fs.checked(Path(workspace.home), directory=True)
    root = fs.checked(home.parent, directory=True)
    work = fs.checked(Path(getattr(workspace, 'round_work', workspace.work)), directory=True)
    if (home.name != 'home' or str(UUID(root.name)) != root.name
            or work.parent != root / 'rounds' or str(UUID(work.name)) != work.name):
        raise ValueError('Skill history does not belong to the workspace')
    return root


def verify(path, item):
    """Old round copies omit empty directories, but never omit or alter a file."""
    safe_directory(path)
    expected = {n: v for n, v in item['entries'].items() if not v.get('directory')}
    allowed_dirs = {n.rstrip('/') for n, v in item['entries'].items() if v.get('directory')}
    contents = {}
    for parent, dirs, files in os.walk(path, followlinks=False):
        for name in dirs:
            directory = Path(parent) / name
            safe_directory(directory)
            if directory.relative_to(path).as_posix() not in allowed_dirs:
                raise ValueError('Unexpected history directory')
        for name in files:
            file = Path(parent) / name
            relative = file.relative_to(path).as_posix()
            info = expected.get(relative)
            if info is None:
                raise ValueError('Unexpected history file')
            data = read_file(file)
            if len(data) != info['size'] or hashlib.sha256(data).hexdigest() != info['sha256']:
                raise ValueError('Historical Skill bytes changed')
            mode = 0o755 if file.suffix.lower() in ('.sh', '.py') else 0o644
            if os.name == 'posix' and stat.S_IMODE(file.stat().st_mode) != mode:
                raise ValueError('Historical Skill file permissions changed')
            contents[relative] = data
    if set(contents) != set(expected):
        raise ValueError('Incomplete historical Skill')
    return contents


def find(root, item):
    safe_directory(root)
    name, checksum = item['name'], item['checksum']
    exact = root / 'skill-history' / checksum / name
    candidates = [exact, *sorted(root.glob('skill-cache/*/' + name)),
                  *sorted(root.glob('rounds/*/skills/' + name))]
    for path in candidates:
        if not os.path.lexists(path):
            continue
        # Links always fail; a different intact version is simply not this content.
        safe_directory(path)
        try:
            return path, verify(path, item)
        except ValueError:
            if path == exact:
                raise
    return None


def _directory(path, uid, gid):
    fs.checked(path, missing=True, directory=True)
    if not path.exists():
        path.mkdir(mode=0o700)
        if os.name == 'posix' and os.geteuid() == 0:
            os.chown(path, uid, gid)
        fs.sync(path)
        fs.sync(path.parent)
    return path


def durable_file(path):
    # Windows cannot fsync a read-only descriptor; production is Linux.
    with fs.reader(path) as stream:
        if os.name == 'posix':
            os.fsync(stream.fileno())


def durable(root, path, item):
    """Fence verified bytes and every directory entry before deleting their central source."""
    root = fs.checked(root, directory=True)
    path = fs.checked(path, directory=True)
    if path == root or not path.is_relative_to(root):
        raise ValueError('Historical Skill durability escaped owner')
    verify(path, item)
    for name, info in item['entries'].items():
        if not info.get('directory'):
            durable_file(path / name)
    directories = [path, *[p for p in path.rglob('*') if p.is_dir()]]
    for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        fs.sync(directory)
    parent = path.parent
    while parent != root:
        fs.sync(parent)
        parent = parent.parent
    lock = root / '.context-prepare.lock'
    if lock.exists():
        durable_file(lock)
    fs.sync(root)
    fs.sync(root.parent)
    if root.parent.name == 'studio':
        fs.sync(root.parent.parent)


def preserve(root, item, read_source):
    """Caller owns task DB locks, has excluded in-flight use, and holds fs.lock."""
    safe_directory(root)
    found = find(root, item)
    if found is not None:
        durable(root, found[0], item)
        return 0
    identity = root.stat()
    base = _directory(root / 'skill-history', identity.st_uid, identity.st_gid)
    version = fs.checked(base / item['checksum'], missing=True, directory=True)
    if version.exists():
        raise ValueError('Incomplete existing historical snapshot')
    temporary = _directory(base / ('.stage-' + uuid4().hex), identity.st_uid, identity.st_gid)
    target = _directory(temporary / item['name'], identity.st_uid, identity.st_gid)
    try:
        for name, info in sorted(item['entries'].items(), key=lambda row: (len(Path(row[0]).parts), row[0])):
            path = target / fs.relative(name.rstrip('/'))
            if info.get('directory'):
                _directory(path, identity.st_uid, identity.st_gid)
            else:
                data = read_source(name)
                if len(data) != info['size'] or hashlib.sha256(data).hexdigest() != info['sha256']:
                    raise ValueError('Historical source integrity mismatch')
                fs.write(path, data)
                path.chmod(0o755 if path.suffix.lower() in ('.sh', '.py') else 0o644)
                if os.name == 'posix' and os.geteuid() == 0:
                    os.chown(path, identity.st_uid, identity.st_gid)
        verify(target, item)
        for directory in sorted((p for p in temporary.rglob('*') if p.is_dir()),
                                key=lambda p: len(p.parts), reverse=True):
            fs.sync(directory)
        fs.sync(temporary)
        temporary.rename(version)
        fs.sync(base)
        durable(root, version / item['name'], item)
        return sum(p.lstat().st_blocks * 512 for p in [version, *version.rglob('*')]) if os.name == 'posix' else sum(
            p.stat().st_size for p in version.rglob('*') if p.is_file())
    finally:
        if temporary.exists():
            import shutil
            fs.checked(temporary, directory=True)
            shutil.rmtree(temporary)
