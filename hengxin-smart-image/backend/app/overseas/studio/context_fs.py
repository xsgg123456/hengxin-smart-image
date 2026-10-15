"""Link-free filesystem operations for the private Studio context."""
import hashlib
import json
import os
import shutil
import stat
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.execution.diagnostics import _safe_read


def relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or any(ord(c) < 32 for c in value) or PurePosixPath(value).is_absolute()
            or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError('Invalid context relative path')
    return value


def checked(path, *, missing=False, directory=None):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Context path must be absolute without traversal')
    if os.name == 'nt' and not str(path).startswith('\\\\?\\'):
        value = str(path)
        path = Path('\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value)
    for part in reversed((path, *path.parents)):
        try:
            info = part.lstat()
        except FileNotFoundError:
            if missing:
                continue
            raise
        if (stat.S_ISLNK(info.st_mode) or getattr(part, 'is_junction', lambda: False)()
                or getattr(info, 'st_file_attributes', 0) & 0x400):
            raise ValueError('Context path cannot contain links')
        if part != path or directory is True:
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError('Context parent must be a directory')
        elif not stat.S_ISDIR(info.st_mode):
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('Context file cannot be linked or special')
        if part == path and directory is False and not stat.S_ISREG(info.st_mode):
            raise ValueError('Context target must be a regular file')
    return path


def mkdir(path):
    path = checked(path, missing=True, directory=True)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return checked(path, directory=True)


def stamp(info):
    # Windows stat() and fstat() report different ctime values after a rename.
    # Identity, size and mtime still fence replacement; content is also hashed.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns if os.name != 'nt' else 0, info.st_nlink)


@contextmanager
def reader(path):
    path = checked(path, directory=False)
    before = path.lstat()
    parent_fd = None
    try:
        if os.name == 'posix':
            parent_fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            for part in path.parts[1:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=parent_fd)
                os.close(parent_fd)
                parent_fd = child
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=parent_fd)
        else:
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0))
        with os.fdopen(fd, 'rb') as stream:
            current = os.fstat(stream.fileno())
            if (not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
                    or stamp(before) != stamp(current)):
                raise ValueError('Context source changed before reading')
            yield stream
            if stamp(current) != stamp(os.fstat(stream.fileno())):
                raise ValueError('Context source changed while reading')
            checked(path, directory=False)
            if stamp(path.lstat()) != stamp(current):
                raise ValueError('Context source replaced while reading')
    finally:
        if parent_fd is not None:
            os.close(parent_fd)


def digest(path):
    checksum, size = hashlib.sha256(), 0
    with reader(path) as stream:
        while chunk := stream.read(1024 * 1024):
            checksum.update(chunk)
            size += len(chunk)
    return checksum.hexdigest(), size


def sync(path):
    if os.name == 'posix':
        fd = os.open(checked(path, directory=True), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


@contextmanager
def writer(path):
    path = checked(path, missing=True, directory=False)
    mkdir(path.parent)
    temporary = path.parent / ('.context-write-' + uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        checked(path, missing=True, directory=False)
        checked(temporary, directory=False)
        os.replace(temporary, path)
        sync(path.parent)
    finally:
        if os.path.lexists(temporary):
            checked(temporary, directory=False).unlink()


def write(path, data):
    with writer(path) as stream:
        stream.write(data)


def copy(source, target, checksum=None):
    digest_value = hashlib.sha256()
    with writer(target) as output:
        with reader(source) as stream:
            while chunk := stream.read(1024 * 1024):
                output.write(chunk)
                digest_value.update(chunk)
        if checksum is not None and digest_value.hexdigest() != checksum:
            raise ValueError('Context source checksum changed')


def load(path):
    checked(path, directory=False)
    return json.loads(_safe_read(path, 32 * 1024 * 1024, allow_windows_fallback=True))


def save(path, data):
    write(path, json.dumps(data, ensure_ascii=False, sort_keys=True,
                           separators=(',', ':'), allow_nan=False).encode())


def space(path, required):
    checked(path, directory=True)
    if shutil.disk_usage(path).free < required + 64 * 1024 * 1024:
        raise ValueError('会话工作区磁盘空间不足，请保留现有文件后释放空间')


@contextmanager
def lock(root, timeout=30):
    """An OS lock survives neither a process crash nor an abandoned preparation."""
    path = checked(root / '.context-prepare.lock', missing=True, directory=False)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    acquired = False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_nlink != 1:
            raise ValueError('Unsafe context lock')
        if os.name == 'nt' and not os.fstat(fd).st_size:
            os.write(fd, b'0')
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ValueError('会话文件正在准备，请稍后重试') from None
                time.sleep(0.05)
        checked(path, directory=False)
        if (path.stat().st_dev, path.stat().st_ino) != (os.fstat(fd).st_dev, os.fstat(fd).st_ino):
            raise ValueError('Context lock was replaced')
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
