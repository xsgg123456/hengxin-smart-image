"""Link-free regular file streams, optionally following an active append-only log."""
import os
import stat
from contextlib import contextmanager
from pathlib import Path


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


def stamp(info):
    # Windows stat() and fstat() report different ctime values after a rename.
    # Identity, size and mtime still fence replacement; content is also hashed.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns if os.name != 'nt' else 0, info.st_nlink)


def _consistent(before, after, growing):
    if growing:
        return (before.st_dev == after.st_dev and before.st_ino == after.st_ino
                and after.st_nlink == 1 and after.st_size >= before.st_size)
    return stamp(before) == stamp(after)


@contextmanager
def reader(path, *, growing=False):
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
                    or not _consistent(before, current, growing)):
                raise ValueError('Context source changed before reading')
            yield stream
            if not _consistent(current, os.fstat(stream.fileno()), growing):
                raise ValueError('Context source changed while reading')
            checked(path, directory=False)
            if not _consistent(current, path.lstat(), growing):
                raise ValueError('Context source replaced while reading')
    finally:
        if parent_fd is not None:
            os.close(parent_fd)
