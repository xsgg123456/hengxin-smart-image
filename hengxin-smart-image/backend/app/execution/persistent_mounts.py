"""Read-only controlled slots inside an otherwise writable conversation work tree."""
import stat
from pathlib import Path


def directory(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Persistent mount must be absolute')
    for part in (path, *path.parents):
        if (part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction())
                or not stat.S_ISDIR(part.lstat().st_mode)):
            raise ValueError('Persistent mount traverses a link or non-directory')
    return path


def regular(path):
    path = Path(path)
    directory(path.parent)
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Persistent mount source is not a private regular file')
    return path


def mounts(workspace):
    work = directory(workspace.work)
    inputs = directory(workspace.inputs_root)
    index = regular(workspace.context_index)
    request = regular(workspace.control / 'input.json')
    for name in ('inputs', 'skills', 'input.json', '.context-files.json'):
        target = work / name
        if target.exists() or target.is_symlink():
            if name in ('inputs', 'skills'):
                directory(target)
            else:
                regular(target)
    return ['--ro-bind', str(inputs), '/work/inputs',
            '--ro-bind', str(request), '/work/input.json',
            '--ro-bind', str(index), '/work/.context-files.json',
            '--tmpfs', '/work/skills']
