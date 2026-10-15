"""Remove only task-private UUID workspaces; sandbox tool shims are unlinked safely."""
import os
import re
import shutil
import stat
from pathlib import Path
from uuid import UUID


def linked(path):
    return path.is_symlink() or bool(getattr(path, 'is_junction', lambda: False)())


def tool_link(parts, target):
    return (shutil.rmtree.avoids_symlink_attacks and len(parts) == 6
        and parts[:4] == ('home', '.codex', 'tmp', 'arg0')
        and re.fullmatch(r'codex-arg0[A-Za-z0-9]+', parts[4]) is not None
        and parts[5] in ('apply_patch', 'applypatch', 'codex-execve-wrapper', 'codex-linux-sandbox')
        and target == '/opt/codex')


def inspect_fd(descriptor, device, parts=()):
    for entry in os.scandir(descriptor):
        info = entry.stat(follow_symlinks=False)
        relative = (*parts, entry.name)
        if stat.S_ISLNK(info.st_mode):
            if not tool_link(relative, os.readlink(entry.name, dir_fd=descriptor)):
                raise ValueError('Unexpected workspace link')
        elif stat.S_ISDIR(info.st_mode):
            if info.st_dev != device:
                raise ValueError('Workspace crosses a mount')
            child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            try:
                inspect_fd(child, device, relative)
            finally:
                os.close(child)
        elif stat.S_ISSOCK(info.st_mode) or stat.S_ISFIFO(info.st_mode):
            continue  # Private dead-session IPC endpoints are unlinked, never opened.
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Workspace contains non-private material')


def clean(root, conversation_id):
    root = Path(root).absolute() / 'api-edits'
    name = str(UUID(str(conversation_id)))
    if os.name == 'posix':
        # Resolve every ancestor using O_NOFOLLOW, including the configured root.
        descriptor = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in root.parts[1:]:
                try:
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                except FileNotFoundError:
                    return
                os.close(descriptor)
                descriptor = child
            try:
                target = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            except FileNotFoundError:
                return
            try:
                inspect_fd(target, os.fstat(target).st_dev)
            finally:
                os.close(target)
            if not shutil.rmtree.avoids_symlink_attacks:
                raise RuntimeError('Safe directory removal is unavailable')
            shutil.rmtree(name, dir_fd=descriptor)
            try:
                os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                return
            raise OSError('Workspace remains after deletion')
        finally:
            os.close(descriptor)
    # Isolated Windows tests and local development; never follow junctions.
    target = root / name
    for parent in (target, *target.parents):
        if linked(parent):
            raise ValueError('Linked execution root')
    if not target.exists():
        return
    for directory, folders, files in os.walk(target, followlinks=False):
        for entry in folders + files:
            path = Path(directory) / entry
            if linked(path) or (path.is_file() and path.stat().st_nlink != 1):
                raise ValueError('Linked workspace material')
    shutil.rmtree(target)
    if target.exists() or linked(target):
        raise OSError('Workspace remains after deletion')
