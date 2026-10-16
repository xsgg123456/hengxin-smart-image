"""Complete, bounded, link-free Skill trees shared by deployment and execution."""
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import yaml

from app.core.skill_package import validate_files as validate_package
from .schemas import validate_files

MAX_FILE = 64 * 1024 * 1024
MAX_TREE = 256 * 1024 * 1024
MAX_ENTRIES = 2000
NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,99}')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def safe_directory(path, *, protected=False):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Skill directory must be absolute')
    for parent in reversed((path, *path.parents)):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or parent.is_symlink() or (
                hasattr(parent, 'is_junction') and parent.is_junction()):
            raise ValueError('Skill directory cannot contain links')
    if protected:
        protect(path, path.stat())
    return path


def protect(path, info):
    if os.name != 'posix' or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('Skill release must be root-owned and not writable by Worker')
    if os.geteuid() != 0 and os.access(path, os.W_OK):
        raise ValueError('Worker cannot have write access to Skill release')


def read_file(path, *, protected=False):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or path.is_symlink() or info.st_nlink != 1
            or info.st_size > MAX_FILE):
        raise ValueError('Skill file is unsafe or too large')
    if protected:
        protect(path, info)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError('Skill changed during validation')
        data = stream.read(MAX_FILE + 1)
        after = os.fstat(stream.fileno())
    if len(data) != info.st_size or (before.st_mtime_ns, before.st_ctime_ns) != (after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('Skill changed during validation')
    return data


def tree(path, *, protected=False):
    root = safe_directory(path, protected=protected)
    files, entries, pending, count, total = {}, {}, [root], 0, 0
    while pending:
        parent = pending.pop()
        for child in sorted(parent.iterdir()):
            count += 1
            if count > MAX_ENTRIES:
                raise ValueError('Skill tree has too many entries')
            relative = child.relative_to(root).as_posix()
            validate_files({'SKILL.md': 'validation', **{relative: 'validation'}})
            info = child.lstat()
            if child.is_symlink() or (hasattr(child, 'is_junction') and child.is_junction()):
                raise ValueError('Skill tree cannot contain links')
            if stat.S_ISDIR(info.st_mode):
                if protected:
                    protect(child, info)
                entries[relative + '/'] = {'directory': True}
                pending.append(child)
                continue
            content = read_file(child, protected=protected)
            total += len(content)
            if total > MAX_TREE:
                raise ValueError('Skill tree is too large')
            files[relative] = content
            entries[relative] = dict(sha256=hashlib.sha256(content).hexdigest(), size=len(content))
    if not files.get('SKILL.md'):
        raise ValueError('Skill tree is missing SKILL.md')
    validate_files({key: 'validation' for key in files})
    try:
        package = validate_package(files, 'text', None, digest(entries))
    except yaml.YAMLError as error:
        raise ValueError('Invalid Skill YAML metadata') from error
    if not NAME.fullmatch(package.name):
        raise ValueError('Invalid Skill name')
    check_references(files)
    return package, entries


def tree_stamp(path, *, protected=False):
    """Metadata cache key: additions, removals, bytes/ACL edits and links invalidate."""
    root = safe_directory(path, protected=protected)
    pending, stamps = [root], []
    while pending:
        parent = pending.pop()
        for child in sorted(parent.iterdir()):
            if len(stamps) >= 50000:
                raise ValueError('Skill release has too many entries')
            info = child.lstat()
            if (child.is_symlink() or (hasattr(child, 'is_junction') and child.is_junction())
                    or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))):
                raise ValueError('Skill release cannot contain links or special files')
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise ValueError('Skill release cannot contain hard links')
            if protected:
                protect(child, info)
            stamps.append((child.relative_to(root).as_posix(), info.st_dev, info.st_ino,
                           info.st_mode, info.st_uid, info.st_gid, info.st_nlink,
                           info.st_size, info.st_mtime_ns, info.st_ctime_ns))
            if stat.S_ISDIR(info.st_mode):
                pending.append(child)
    return tuple(stamps)


def check_references(files):
    """Reject missing literal Markdown package resources, including reference pages."""
    for filename, data in files.items():
        if not filename.endswith('.md'):
            continue
        document = data.decode('utf-8-sig')
        for match in re.finditer(r'\[[^\]\n]*\]\(([^)\n]+)\)', document):
            target = match.group(1).strip().split(' "', 1)[0].strip('<>')
            if not target or target.startswith('#') or urlsplit(target).scheme:
                continue
            relative = unquote(target.split('#', 1)[0])
            # Only literal bundled resource paths; generic prose links remain prose.
            if not relative or not any(part in relative for part in ('references/', 'assets/', 'scripts/', 'SKILL.md')):
                continue
            parts = []
            for part in (PurePosixPath(filename).parent / relative).parts:
                if part == '..':
                    if not parts:
                        raise ValueError('Skill reference escapes package')
                    parts.pop()
                elif part != '.':
                    parts.append(part)
            if '/'.join(parts) not in files:
                raise ValueError('Skill reference is missing: ' + relative)
