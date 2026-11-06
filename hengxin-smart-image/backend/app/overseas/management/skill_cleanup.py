"""Bounded, resumable reclamation of central Skill trees; never session files."""
import json
import os
import shutil
import stat
from pathlib import Path
from uuid import UUID

from . import installed_catalog as catalog
from .installed_tree import NAME, read_file, safe_directory, tree
from .skill_transfer_store import sync_directory


def allocated(path, *, exclude=()):
    if not os.path.lexists(path):
        return 0
    info = path.lstat()
    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
        raise ValueError('Cleanup refuses linked storage')
    if not stat.S_ISDIR(info.st_mode) and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise ValueError('Cleanup refuses special or shared files')
    size = info.st_blocks * 512 if os.name == 'posix' else (info.st_size if path.is_file() else 0)
    return size + (sum(allocated(p) for p in path.iterdir() if p.name not in exclude) if path.is_dir() else 0)


def library_footprint(store):
    return allocated(store.installed_root, exclude=('.pending.json', '.preparing.json'))


def footprint(store):
    return library_footprint(store) + allocated(store.path)


def target(store, entry):
    """Revalidate persisted relative plans on every retry, even after partial rmtree."""
    scope, relative = entry['scope'], entry['path']
    parts = relative.split('/')
    if scope == 'library':
        root = store.installed_root
        valid = len(parts) == 3 and (
            parts[0] == 'releases' and catalog.HASH.fullmatch(parts[1]) and NAME.fullmatch(parts[2])
            or parts[0] == 'packages' and NAME.fullmatch(parts[1]) and catalog.HASH.fullmatch(parts[2]))
    elif scope == 'transfers':
        root = store.path
        valid = len(parts) == 2 and parts[1] == 'package' and str(UUID(parts[0])) == parts[0]
    else:
        raise ValueError('Unknown cleanup scope')
    if not valid:
        raise ValueError('Unsafe cleanup destination')
    safe_directory(root, protected=store.protected)
    path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Cleanup escaped approved root')
    safe_directory(path.parent, protected=store.protected)
    if os.path.lexists(path):
        safe_directory(path, protected=store.protected)
        allocated(path)  # Reject links, hardlinks and device files before deleting anything.
    return path


def plan(store, names, retained, before_bytes, history_bytes=0, transfer_id=None):
    """Retained entries have already been published as verified independent objects."""
    root, entries = store.installed_root, []
    keep = set(retained)
    for directory in sorted((root / 'releases').iterdir()):
        if not catalog.HASH.fullmatch(directory.name):
            continue
        _, manifest = catalog.release_manifest(root, directory.name, store.protected)
        for item in manifest['items']:
            path = directory / item['name']
            if item['name'] not in names or not os.path.lexists(path):
                continue
            catalog.verify_package(directory, item, store.protected)
            key = (item['name'], item['checksum'])
            if key in keep:
                replacement = root / 'packages' / key[0] / key[1]
                if not replacement.exists():
                    continue  # Active legacy jobs remain pinned until their bytes are migrated.
                package, actual = tree(replacement, protected=store.protected)
                if package.checksum != key[1] or actual != item['entries']:
                    raise ValueError('Retained replacement is not identical')
            entries.append(dict(scope='library', path=path.relative_to(root).as_posix()))
    packages = root / 'packages'
    if packages.exists():
        safe_directory(packages, protected=store.protected)
        for name in sorted(names):
            if not NAME.fullmatch(name):
                raise ValueError('Invalid cleanup Skill name')
            parent = packages / name
            if not parent.exists():
                continue
            safe_directory(parent, protected=store.protected)
            for path in sorted(parent.iterdir()):
                if not catalog.HASH.fullmatch(path.name) or (name, path.name) in keep:
                    continue
                package, _ = tree(path, protected=store.protected)
                if package.name != name or package.checksum != path.name:
                    raise ValueError('Unverified orphan Skill object')
                entries.append(dict(scope='library', path=path.relative_to(root).as_posix()))
    for folder in sorted(store.path.iterdir()):
        if not folder.is_dir() or not (folder / 'state.json').exists():
            continue
        safe_directory(folder, protected=store.protected)
        state = json.loads(read_file(folder / 'state.json', protected=store.protected))
        if (state.get('package', {}).get('name') in names
                and (state['status'] == 'installed' or state['id'] == transfer_id)
                and os.path.lexists(folder / 'package')):
            entries.append(dict(scope='transfers', path=folder.name + '/package'))
    for entry in entries:
        target(store, entry)
    return dict(schema=1, targets=entries, beforeBytes=before_bytes, historyBytes=history_bytes)


def execute(store, cleanup):
    from . import skill_preparation as preparation
    if cleanup.get('schema') != 1:
        raise ValueError('Unknown cleanup journal')
    baseline = preparation.load(store.installed_root, store.protected)
    if baseline and (cleanup['beforeBytes'] != baseline['beforeBytes']):
        raise ValueError('Cleanup accounting does not match preparation')
    history_bytes = preparation.history_bytes(baseline) if baseline else cleanup['historyBytes']
    # Validate the entire remaining scope before the first mutation.
    paths = [target(store, entry) for entry in cleanup['targets']]
    for path in paths:
        if path.exists():
            shutil.rmtree(path)
            sync_directory(path.parent)
        if os.path.lexists(path):
            raise OSError('Skill physical deletion is incomplete')
    # Include manifests, newly prepared objects and preserved private history in net savings.
    return max(0, cleanup['beforeBytes'] - footprint(store) - history_bytes)
