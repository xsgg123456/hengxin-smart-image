"""Recover only the recognizable, never-published empty catalog bootstrap."""
import json
import re
from pathlib import Path

from .installed_tree import digest, read_file, safe_directory
from .skill_transfer_store import atomic_json

EMPTY = {'schema': 2, 'items': []}
EMPTY_ID = digest(EMPTY)
STAGING = re.compile(r'^\.install-[a-zA-Z0-9_-]{8}$')
TEMPORARY = re.compile(r'^\.write-[a-zA-Z0-9_-]{8}$')


def needs_recovery(root):
    """A genuinely empty root and an intact preparation journal need no repair."""
    if (root / 'current.json').exists() or (root / 'current.json').is_symlink():
        return False
    return bool({item.name for item in root.iterdir()} - {'.preparing.json'})


def scratch(path, protected, exact_values):
    data = read_file(path, protected=protected)
    matches = any(value.startswith(data) for value in exact_values)
    if len(data) > 2 * 1024 * 1024 or not matches:
        raise ValueError('Unknown Skill initialization temporary file')


def inventory(root, protected):
    """Prove every leftover belongs to first-empty-catalog setup before mutation."""
    from . import installed_catalog as catalog
    root = safe_directory(Path(root), protected=protected)
    releases = root / 'releases'
    manifest_bytes = json.dumps(EMPTY, ensure_ascii=False, sort_keys=True).encode()
    pointer_bytes = json.dumps({'release': EMPTY_ID}, ensure_ascii=False, sort_keys=True).encode()
    for item in root.iterdir():
        if item.name == '.preparing.json':
            from .skill_preparation import load
            load(root, protected)
        elif item.name == 'releases':
            safe_directory(releases, protected=protected)
            for child in releases.iterdir():
                if child.name == EMPTY_ID:
                    _, manifest = catalog.release_manifest(root, EMPTY_ID, protected)
                    if manifest != EMPTY:
                        raise ValueError('Unexpected initial Skill release')
                elif STAGING.fullmatch(child.name):
                    safe_directory(child, protected=protected)
                    for file in child.iterdir():
                        if file.name == 'manifest.json':
                            if read_file(file, protected=protected) != manifest_bytes:
                                raise ValueError('Unexpected initial Skill manifest')
                        elif TEMPORARY.fullmatch(file.name):
                            scratch(file, protected, [manifest_bytes])
                        else:
                            raise ValueError('Unknown initial Skill staging content')
                else:
                    raise ValueError('Unknown Skill release without a catalog')
        elif TEMPORARY.fullmatch(item.name):
            scratch(item, protected, [pointer_bytes])
        else:
            raise ValueError('Unknown Skill data without a catalog')


def recover(root, protected=False):
    """Restore the empty index; unknown files are left untouched and rejected."""
    root = safe_directory(Path(root), protected=protected)
    if not needs_recovery(root):
        return False
    inventory(root, protected)
    from .skill_objects import write_release
    release = write_release(root, [], protected)
    if release != EMPTY_ID:
        raise ValueError('Initial Skill release identity mismatch')
    atomic_json(root / 'current.json', {'release': release})
    # Pre-existing staging is retained: a filename alone does not prove ownership.
    return True
