"""Conversation-private, content-addressed Skills; never erase historical work."""
import hashlib
import json
import os
import re
import shutil
import stat
from pathlib import Path
from uuid import UUID, uuid4

from app.overseas.studio import context_fs as fs
from .skill_content import describe


def owner(workspace):
    home = fs.checked(workspace.home, directory=True)
    root = fs.checked(home.parent, directory=True)
    work = fs.checked(workspace.round_work, directory=True)
    if (home.name != 'home' or str(UUID(root.name)) != root.name
            or work.parent != root / 'rounds' or str(UUID(work.name)) != work.name
            or fs.checked(workspace.work, directory=True) != root / 'persistent' / 'work'
            or fs.checked(workspace.control, directory=True) != root / 'control' / work.name):
        raise ValueError('Skill cache does not belong to conversation')
    return root


def verify(root, entries):
    """Verify exact paths, bytes and permissions, including unexpected directories."""
    fs.checked(root, directory=True)
    directories = {p.as_posix() for name in entries for p in Path(name).parents if str(p) != '.'}
    found, seen_dirs = set(), set()
    pending = [root]
    while pending:
        parent = pending.pop()
        fs.checked(parent, directory=True)
        for path in parent.iterdir():
            fs.checked(path)
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                if relative not in directories:
                    raise ValueError('Unexpected Skill cache directory')
                seen_dirs.add(relative)
                pending.append(path)
            else:
                item = entries.get(relative)
                if item is None or fs.digest(path) != (item['checksum'], item['size']):
                    raise ValueError('Skill cache integrity mismatch')
                if os.name == 'posix' and stat.S_IMODE(path.stat().st_mode) != item['mode']:
                    raise ValueError('Skill cache permissions changed')
                found.add(relative)
    if found != set(entries) or seen_dirs != directories:
        raise ValueError('Skill cache is incomplete')


def prepare(skill, workspace, get_store):
    root = owner(workspace)
    name, entries, read = describe(skill, get_store, workspace)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', name) or 'SKILL.md' not in entries:
        raise ValueError('Invalid frozen Skill identity')
    identity = hashlib.sha256(json.dumps([name, entries], sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    with fs.lock(root):
        cache = fs.mkdir(root / 'skill-cache')
        version = fs.checked(cache / identity, missing=True, directory=True)
        target = version / name
        if version.exists():
            if {p.name for p in version.iterdir()} != {name}:
                raise ValueError('Unexpected Skill cache version files')
            verify(target, entries)
        else:
            fs.space(cache, sum(item['size'] for item in entries.values()))
            temporary = fs.mkdir(cache / ('.stage-' + uuid4().hex))
            try:
                package = fs.mkdir(temporary / name)
                for relative, item in entries.items():
                    content = read(relative)
                    if (not isinstance(content, bytes) or len(content) != item['size']
                            or hashlib.sha256(content).hexdigest() != item['checksum']):
                        raise ValueError('Frozen Skill resource integrity mismatch')
                    path = package / fs.relative(relative)
                    fs.write(path, content)
                    path.chmod(item['mode'])
                verify(package, entries)
                fs.sync(temporary)
                fs.checked(version, missing=True, directory=True)
                os.rename(temporary, version)
                fs.sync(cache)
            finally:
                if temporary.exists():
                    fs.checked(temporary, directory=True)
                    if temporary.parent != cache or not temporary.name.startswith('.stage-'):
                        raise ValueError('Invalid Skill staging cleanup target')
                    shutil.rmtree(temporary)
        fs.save(Path(workspace.control) / 'skill-ref.json',
                dict(version=1, name=name, content=identity))
    workspace.skill_name = name
    workspace.local_skill = target
