"""Immutable per-Skill objects and small content-addressed release indexes."""
import os
import shutil
import tempfile
from pathlib import Path

from . import installed_catalog as catalog
from .installed_tree import digest, safe_directory, tree
from .skill_transfer_store import atomic_json, sync_directory


def ensure_directory(path, protected):
    existed = path.exists()
    path.mkdir(exist_ok=True, mode=0o755)
    result = safe_directory(path, protected=protected)
    if not existed:
        sync_directory(path.parent)
    return result


def write_release(root, items, protected):
    releases = ensure_directory(root / 'releases', protected)
    manifest = dict(schema=2, items=sorted(items, key=lambda row: row['name']))
    release = digest(manifest)
    target = releases / release
    staging = Path(tempfile.mkdtemp(prefix='.install-', dir=releases))
    try:
        staging.chmod(0o755)
        atomic_json(staging / 'manifest.json', manifest)
        for item in items:
            catalog.verify_package(staging, item, protected)
        sync_directory(staging)
        if not target.exists():
            staging.rename(target)
            sync_directory(releases)
        directory, saved = catalog.release_manifest(root, release, protected)
        for item in saved['items']:
            catalog.verify_package(directory, item, protected)
        return release
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def copy_object(root, item, source, protected):
    """Copy validated bytes once; staging never becomes a published object early."""
    package, entries = tree(source)
    if (package.name != item['name'] or package.description != item['description']
            or package.checksum != item['checksum'] or entries != item['entries']):
        raise ValueError('Skill publication source differs from its manifest')
    packages = ensure_directory(root / 'packages', protected)
    parent = ensure_directory(packages / item['name'], protected)
    destination = parent / item['checksum']
    staging = Path(tempfile.mkdtemp(prefix='.install-', dir=parent))
    try:
        staging.chmod(0o755)
        copied = staging / item['name']
        copied.mkdir(mode=0o755)
        for relative, info in entries.items():
            path = copied / relative
            if info.get('directory'):
                path.mkdir(parents=True, exist_ok=True, mode=0o755)
                continue
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            with path.open('wb') as output:
                output.write(package.files[relative])
                output.flush()
                os.fsync(output.fileno())
            executable = (source / relative).stat().st_mode & 0o111 or path.suffix.lower() in ('.sh', '.py')
            path.chmod(0o755 if executable else 0o644)
        catalog.verify_package(staging, item, protected)
        for path in sorted(copied.rglob('*'), key=lambda row: len(row.parts), reverse=True):
            if path.is_dir():
                sync_directory(path)
        sync_directory(copied)
        if not destination.exists():
            copied.rename(destination)
            sync_directory(parent)
        actual, actual_entries = tree(destination, protected=protected)
        if actual.checksum != item['checksum'] or actual_entries != entries:
            raise ValueError('Skill object integrity mismatch')
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def prepare_release(root, items, replacement_sources=None, *, protected=False):
    """Caller serializes publication and owns pointer/DB transactions and GC."""
    root = safe_directory(Path(root), protected=protected)
    from .skill_initialization import recover
    recover(root, protected)
    previous, old_items = catalog.read_catalog(root, protected)
    if previous is None:
        # Any later copy failure still leaves a valid, explicitly empty catalog.
        empty = write_release(root, [], protected)
        atomic_json(root / 'current.json', {'release': empty})
    sources = replacement_sources or {}
    for item in items:
        catalog.validate_item(item)
        destination = root / 'packages' / item['name'] / item['checksum']
        if destination.exists() or destination.is_symlink():
            for path in (root / 'packages', destination.parent):
                safe_directory(path, protected=protected)
            package, entries = tree(destination, protected=protected)
            if (package.name != item['name'] or package.description != item['description']
                    or package.checksum != item['checksum'] or entries != item['entries']):
                raise ValueError('Existing Skill object integrity mismatch')
            continue
        source = sources.get(item['name'])
        if source is None:
            old = next((row for row in old_items if row['name'] == item['name']
                        and row['checksum'] == item['checksum']), None)
            if old is None:
                raise ValueError('Missing Skill publication source')
            directory, _ = catalog.release_manifest(root, previous, protected)
            source = catalog.package_directory(directory, old, protected)
        copy_object(root, item, Path(source), protected)
    return write_release(root, items, protected)
