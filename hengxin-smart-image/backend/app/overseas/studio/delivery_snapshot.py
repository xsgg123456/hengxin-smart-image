"""Immutable delivery bytes; callers own job authorization, process exit and lease.

``control`` is the backend-private receipt root (workspace.control / 'delivery'),
outside the model mounts. This module never reads work files or invokes a model.
"""
from . import context_fs as fs
from .delivery_snapshot_fs import (canonical_target, check_image, check_manifest,
                                   identity_value, metadata, read_image, read_manifest,
                                   root_path, save_manifest, snapshot_path)


def _recover(root, manifest):
    changed = False
    for row in manifest['items']:
        if row['status'] == 'capturing' and snapshot_path(root, row).exists():
            read_image(root, row)
            fs.sync(snapshot_path(root, row).parent)
            row['status'] = 'captured'
            changed = True
    if changed:
        manifest['ready'] = all(row['status'] == 'captured' for row in manifest['items'])
        save_manifest(root, manifest)
    # A previous process may have stopped after manifest rename but before fsync.
    fs.sync(root)
    return manifest


def begin(control, identity: dict, reply: str, session_id: str, targets: list[str]) -> dict:
    """Persist the complete expected ordered set before reading any source image."""
    if not isinstance(targets, list):
        raise ValueError('Invalid delivery targets')
    proposed = dict(version=1, identity=identity_value(identity, session_id), finalText=reply,
                    targets=list(targets), ready=not targets,
                    items=[dict(target=target, order=order, status='pending',
                                snapshot=f'snapshots/{order:04d}.bin')
                           for order, target in enumerate(targets)])
    check_manifest(proposed)
    root = root_path(control, create=True)
    with fs.lock(root):
        existing = read_manifest(root)
        if existing is not None:
            if any(existing[k] != proposed[k] for k in ('identity', 'finalText', 'targets')):
                raise ValueError('Delivery manifest identity or final reply mismatch')
            return _recover(root, existing)
        save_manifest(root, proposed)
        return proposed


def load(control) -> dict | None:
    """Load and finish interrupted file commits without consulting mutable originals."""
    root = root_path(control)
    if not root.exists():
        return None
    with fs.lock(root):
        manifest = read_manifest(root)
        return _recover(root, manifest) if manifest is not None else None


def capture(control, target: str, image) -> dict:
    """Freeze one validated image; retries cannot change its bytes or identity."""
    image = check_image(image)
    root = root_path(control)
    with fs.lock(root):
        manifest = read_manifest(root)
        if manifest is None:
            raise ValueError('Delivery manifest is missing')
        row = next((row for row in manifest['items']
                    if canonical_target(row['target']) == canonical_target(target)), None)
        if row is None:
            raise ValueError('Unexpected delivery target')
        expected = metadata(manifest['identity'], row['target'], image)
        if row['status'] != 'pending':
            if any(row[k] != value for k, value in expected.items()):
                raise ValueError('Delivery snapshot is immutable')
            if row['status'] == 'captured':
                read_image(root, row)
                return _recover(root, manifest)
        else:
            row.update(expected, status='capturing')
            save_manifest(root, manifest)
        destination = snapshot_path(root, row)
        if destination.exists():
            read_image(root, row)
            fs.sync(destination.parent)
        else:
            fs.mkdir(destination.parent)
            fs.sync(root)
            fs.write(destination, image.data)
        row['status'] = 'captured'
        manifest['ready'] = all(item['status'] == 'captured' for item in manifest['items'])
        save_manifest(root, manifest)
        return manifest


def images(control, manifest=None, *, captured_only=False):
    """Yield (target, ValidatedImage, item) in final order, checking every file.

    Partial upload callers may request captured_only=True. Uncaptured items are
    then omitted deliberately; a damaged captured file always raises explicitly.
    An optional earlier manifest binds this read to the same immutable receipt.
    """
    current = load(control)
    if current is None:
        raise ValueError('Delivery manifest is missing')
    if manifest is not None:
        check_manifest(manifest)
        if any(manifest[k] != current[k] for k in ('identity', 'finalText', 'targets')):
            raise ValueError('Delivery manifest identity or final reply mismatch')
    if not captured_only and not current['ready']:
        raise ValueError('Delivery capture is incomplete')
    root = root_path(control)
    for row in current['items']:
        if row['status'] == 'captured':
            yield row['target'], read_image(root, row), dict(row)
