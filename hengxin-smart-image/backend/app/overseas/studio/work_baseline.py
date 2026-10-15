"""Snapshot existing work images before launch, without accepting them as delivery."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat

from app.execution.final_delivery import _PROTECTED
from app.execution.output_collector import OutputCollectionError

IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.webp'})
_CHUNK_BYTES = 1024 * 1024
_DESCRIPTORS = (os.open in os.supports_dir_fd and os.scandir in os.supports_fd
                and hasattr(os, 'O_NOFOLLOW'))


def _version(info, *, cross_handle=False):
    # Python 3.12 on Windows reports different ctime semantics for stat/fstat.
    ctime = None if os.name == 'nt' and cross_handle else info.st_ctime_ns
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            ctime, info.st_nlink)


def _no_links(path):
    for component in (path, *path.parents):
        info = component.lstat()
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & 0x400):
            raise ValueError('linked work path')


def _directory_fd(path):
    """Open every ancestor without following links on production POSIX hosts."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(path.anchor, flags)
    try:
        for name in path.parts[1:]:
            child = os.open(name, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _digest(path, parent_fd, expected):
    if parent_fd is None:
        _no_links(path)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0))
    else:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=parent_fd)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or _version(before, cross_handle=True) != _version(expected, cross_handle=True)):
            raise ValueError('unsafe work image')
        digest, count = hashlib.sha256(), 0
        while chunk := stream.read(_CHUNK_BYTES):
            digest.update(chunk)
            count += len(chunk)
        after = os.fstat(stream.fileno())
        if _version(before) != _version(after) or count != before.st_size:
            raise ValueError('changed work image')
    current = (path.lstat() if parent_fd is None else
               os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False))
    if _version(current) != _version(expected):
        raise ValueError('replaced work image')
    if parent_fd is None:
        _no_links(path)
    return digest.hexdigest()


def _scan(path, relative, descriptor, result):
    if descriptor is None:
        _no_links(path)
    before = path.lstat() if descriptor is None else os.fstat(descriptor)
    if not stat.S_ISDIR(before.st_mode):
        raise ValueError('invalid work directory')
    with os.scandir(path if descriptor is None else descriptor) as entries:
        for entry in entries:
            # The same protected path components can never become output candidates.
            if entry.name in _PROTECTED:
                continue
            child, name = path / entry.name, relative / entry.name
            # Windows DirEntry.stat omits inode/device/link count; lstat does not.
            info = child.lstat() if descriptor is None else entry.stat(follow_symlinks=False)
            if (stat.S_ISLNK(info.st_mode)
                    or getattr(info, 'st_file_attributes', 0) & 0x400):
                raise ValueError('linked work entry')
            if stat.S_ISDIR(info.st_mode):
                child_fd = None if descriptor is None else os.open(
                    entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor)
                try:
                    opened = child.lstat() if child_fd is None else os.fstat(child_fd)
                    if _version(opened) != _version(info):
                        raise ValueError('replaced work directory')
                    _scan(child, name, child_fd, result)
                finally:
                    if child_fd is not None:
                        os.close(child_fd)
            elif not stat.S_ISREG(info.st_mode):
                raise ValueError('invalid work entry')
            elif child.suffix.lower() in IMAGE_EXTENSIONS:
                result[_key(name)] = _digest(child, descriptor, info)
    after = path.lstat() if descriptor is None else os.fstat(descriptor)
    if _version(before) != _version(after):
        raise ValueError('changed work directory')
    if descriptor is None:
        _no_links(path)


def _key(relative):
    name = relative.as_posix()
    return os.path.normcase(name).replace('\\', '/') if os.name == 'nt' else name


def snapshot_work(work: Path) -> dict[str, str]:
    """Call after material preparation and before CLI launch; never ignore failure."""
    descriptor = None
    try:
        work = Path(work).absolute()
        if '..' in work.parts:
            raise ValueError('parent traversal')
        descriptor = _directory_fd(work) if _DESCRIPTORS else None
        result = {}
        _scan(work, PurePosixPath(), descriptor, result)
        if descriptor is not None:
            _no_links(work)
            if _version(work.lstat()) != _version(os.fstat(descriptor)):
                raise ValueError('replaced work root')
        return result
    except (OSError, ValueError, TypeError, RecursionError):
        raise OutputCollectionError('work_baseline_failed') from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def check_work_version(path: Path, work: Path, baseline, checksum: str):
    """Compare the actual validated bytes, not a separately reopened candidate."""
    if not isinstance(baseline, dict) or any(
        not isinstance(name, str) or not name or PurePosixPath(name).is_absolute()
        or any(part in ('', '.', '..') for part in name.split('/'))
        or not isinstance(value, str)
        or not re.fullmatch(r'[0-9a-f]{64}', value)
        for name, value in baseline.items()
    ):
        raise OutputCollectionError('work_baseline_failed')
    name = _key(path.absolute().relative_to(Path(work).absolute()))
    if baseline.get(name) == checksum:
        raise OutputCollectionError('historical_output_forbidden')
