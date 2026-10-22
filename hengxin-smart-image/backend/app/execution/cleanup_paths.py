"""Descriptor-anchored reclamation of UUID workspaces and their private caches."""
from contextlib import ExitStack
import os
import re
import shutil
import stat
from pathlib import Path
from uuid import UUID


class CleanupSafetyError(ValueError):
    """A static classification, safe to include in operational diagnostics."""

    CODES = frozenset({'UNEXPECTED_LINK', 'CROSS_DEVICE', 'NON_PRIVATE_MATERIAL',
                      'UNSAFE_REMOVAL', 'ROOT_INVALID', 'TARGET_CHANGED'})

    def __init__(self, code):
        self.code = code if code in self.CODES else 'UNSAFE_REMOVAL'
        super().__init__(self.code)


def linked(path):
    return path.is_symlink() or bool(getattr(path, 'is_junction', lambda: False)())


def tool_link(parts, target):
    return (len(parts) == 6 and parts[:4] == ('home', '.codex', 'tmp', 'arg0')
        and re.fullmatch(r'codex-arg0[A-Za-z0-9]+', parts[4]) is not None
        and parts[5] in ('apply_patch', 'applypatch', 'codex-execve-wrapper', 'codex-linux-sandbox')
        and target == '/opt/codex')


def _same(before, after):
    return (before.st_dev, before.st_ino, stat.S_IFMT(before.st_mode)) == (
        after.st_dev, after.st_ino, stat.S_IFMT(after.st_mode))


def _directory(info, device=None):
    if stat.S_ISLNK(info.st_mode):
        raise CleanupSafetyError('UNEXPECTED_LINK')
    if not stat.S_ISDIR(info.st_mode):
        raise CleanupSafetyError('ROOT_INVALID')
    if device is not None and info.st_dev != device:
        raise CleanupSafetyError('CROSS_DEVICE')


def _mount_id(descriptor):
    """Device IDs do not distinguish bind mounts; require kernel FD evidence."""
    try:
        lines = Path(f'/proc/self/fdinfo/{descriptor}').read_text(encoding='ascii').splitlines()
    except (OSError, UnicodeError):
        raise CleanupSafetyError('UNSAFE_REMOVAL') from None
    for line in lines:
        if re.fullmatch(r'mnt_id:\s+[0-9]+', line):
            return int(line.split(':', 1)[1])
    raise CleanupSafetyError('UNSAFE_REMOVAL')


def _open_child(parent, name, device=None):
    try:
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None
    _directory(before, device)
    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        if not _same(before, os.fstat(child)):
            raise CleanupSafetyError('TARGET_CHANGED')
        if device is not None and _mount_id(parent) != _mount_id(child):
            raise CleanupSafetyError('CROSS_DEVICE')
    except BaseException:
        os.close(child)
        raise
    return child


def _inspect_leaf_mount(parent, name, expected):
    child = os.open(name, os.O_PATH | os.O_NOFOLLOW, dir_fd=parent)
    try:
        if not _same(expected, os.fstat(child)):
            raise CleanupSafetyError('TARGET_CHANGED')
        if _mount_id(parent) != _mount_id(child):
            raise CleanupSafetyError('CROSS_DEVICE')
    finally:
        os.close(child)


def _walk_fd(descriptor, device, parts=(), remove=False):
    """Use identical boundaries during preflight and every actual removal step."""
    with os.scandir(descriptor) as entries:
        for entry in entries:
            info = entry.stat(follow_symlinks=False)
            relative = (*parts, entry.name)
            if info.st_dev != device:
                raise CleanupSafetyError('CROSS_DEVICE')
            if stat.S_ISLNK(info.st_mode):
                if not tool_link(relative, os.readlink(entry.name, dir_fd=descriptor)):
                    raise CleanupSafetyError('UNEXPECTED_LINK')
            elif stat.S_ISDIR(info.st_mode):
                child = _open_child(descriptor, entry.name, device)
                if child is None:
                    raise CleanupSafetyError('TARGET_CHANGED')
                try:
                    if not _same(info, os.fstat(child)):
                        raise CleanupSafetyError('TARGET_CHANGED')
                    _walk_fd(child, device, relative, remove)
                    if remove:
                        _verify_entry(descriptor, entry.name, info, _mount_id(child))
                        os.rmdir(entry.name, dir_fd=descriptor)
                finally:
                    os.close(child)
            elif (not (stat.S_ISREG(info.st_mode) or stat.S_ISSOCK(info.st_mode)
                       or stat.S_ISFIFO(info.st_mode)) or info.st_nlink != 1):
                raise CleanupSafetyError('NON_PRIVATE_MATERIAL')
            if not stat.S_ISDIR(info.st_mode):
                _inspect_leaf_mount(descriptor, entry.name, info)
                if remove:
                    _verify_entry(descriptor, entry.name, info)
                    os.unlink(entry.name, dir_fd=descriptor)


def inspect_fd(descriptor, device, parts=()):
    """Read-only compatibility entry point; never dereference links or read IPC."""
    _walk_fd(descriptor, device, parts)


def _remove_tree(parent, name, child, device, parts):
    _walk_fd(child, device, parts, remove=True)
    _verify_entry(parent, name, os.fstat(child), _mount_id(child))
    os.rmdir(name, dir_fd=parent)


def _verify_entry(parent, name, expected, mount_id=None):
    try:
        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        raise CleanupSafetyError('TARGET_CHANGED') from None
    if not _same(current, expected):
        raise CleanupSafetyError('TARGET_CHANGED')
    if mount_id is not None:
        child = _open_child(parent, name)
        if child is None:
            raise CleanupSafetyError('TARGET_CHANGED')
        try:
            if not _same(os.fstat(child), expected) or _mount_id(child) != mount_id:
                raise CleanupSafetyError('TARGET_CHANGED')
        finally:
            os.close(child)


def _clean_posix(root, name, cache_only):
    if not all(getattr(os, flag, 0) for flag in ('O_DIRECTORY', 'O_NOFOLLOW', 'O_PATH')):
        raise CleanupSafetyError('UNSAFE_REMOVAL')
    with ExitStack() as stack:
        descriptor = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, descriptor)
        chain = []

        def descend(parent, part, device=None):
            child = _open_child(parent, part, device)
            if child is not None:
                stack.callback(os.close, child)
                chain.append((parent, part, os.fstat(child), _mount_id(child)))
            return child

        for part in root.parts[1:]:
            descriptor = descend(descriptor, part)
            if descriptor is None:
                return
        device = os.fstat(descriptor).st_dev
        target = descend(descriptor, name, device)
        if target is None:
            return
        if cache_only:
            parent = target
            for part in ('home', '.codex'):
                parent = descend(parent, part, device)
                if parent is None:
                    return
            candidates = []
            for part in ('cache', 'plugins'):
                child = _open_child(parent, part, device)
                if child is not None:
                    stack.callback(os.close, child)
                    candidates.append((parent, part, child, ('home', '.codex', part)))
        else:
            candidates = [(descriptor, name, target, ())]
        for _, _, child, parts in candidates:
            inspect_fd(child, device, parts)
        for parent, part, expected, mount_id in chain:
            _verify_entry(parent, part, expected, mount_id)
        # All cache candidates pass preflight before either is removed.
        for parent, part, child, _ in candidates:
            _verify_entry(parent, part, os.fstat(child), _mount_id(child))
        for parent, part, child, parts in candidates:
            _verify_entry(parent, part, os.fstat(child), _mount_id(child))
            _remove_tree(parent, part, child, device, parts)
            try:
                os.stat(part, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise CleanupSafetyError('UNSAFE_REMOVAL')


def _windows_directory(path, device=None):
    if linked(path):
        raise CleanupSafetyError('UNEXPECTED_LINK')
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    _directory(info, device)
    return info


def _inspect_windows(path, device):
    def walk_error(error):
        raise error

    for directory, folders, files in os.walk(path, followlinks=False, onerror=walk_error):
        for name in folders + files:
            child = Path(directory) / name
            if linked(child):
                raise CleanupSafetyError('UNEXPECTED_LINK')
            info = child.lstat()
            if info.st_dev != device:
                raise CleanupSafetyError('CROSS_DEVICE')
            if not stat.S_ISDIR(info.st_mode) and (
                not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            ):
                raise CleanupSafetyError('NON_PRIVATE_MATERIAL')


def _clean_windows(root, name, cache_only):
    target = root / name
    chain = []
    for path in (*reversed(root.parents), root):
        info = _windows_directory(path)
        if info is None:
            return
        chain.append((path, info))
    device = chain[-1][1].st_dev
    info = _windows_directory(target, device)
    if info is None:
        return
    chain.append((target, info))
    if cache_only:
        for part in ('home', '.codex'):
            target = target / part
            info = _windows_directory(target, device)
            if info is None:
                return
            chain.append((target, info))
        paths = [target / part for part in ('cache', 'plugins')]
    else:
        paths = [target]
    candidates = []
    for path in paths:
        info = _windows_directory(path, device)
        if info is not None:
            _inspect_windows(path, device)
            candidates.append((path, info))
    for path, expected in chain + candidates:
        info = _windows_directory(path, device if path in paths else None)
        if info is None or not _same(expected, info):
            raise CleanupSafetyError('TARGET_CHANGED')
    for path, expected in candidates:
        info = _windows_directory(path, device)
        if info is None or not _same(expected, info):
            raise CleanupSafetyError('TARGET_CHANGED')
        shutil.rmtree(path)
        if path.exists() or linked(path):
            raise CleanupSafetyError('UNSAFE_REMOVAL')


def clean(root, resource_id, cache_only=False):
    """Remove one UUID child, or only its cache/plugins; missing paths are a no-op."""
    root = Path(root).absolute()
    try:
        name = str(UUID(str(resource_id)))
    except (ValueError, TypeError, AttributeError):
        raise CleanupSafetyError('ROOT_INVALID') from None
    if '..' in root.parts:
        raise CleanupSafetyError('ROOT_INVALID')
    if os.name == 'posix':
        _clean_posix(root, name, cache_only)
    else:
        _clean_windows(root, name, cache_only)
