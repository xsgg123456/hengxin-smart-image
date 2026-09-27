"""Platform-owned, immutable delivery bytes; manifest is the commit marker."""
import hashlib
import json
import os
import stat
from pathlib import Path
from uuid import UUID, uuid4

from app.modules.files.validation import FORMATS, MAX_UPLOAD_BYTES, ValidatedImage, safe_name

MANIFEST = 'delivery-snapshot.json'
MAX_MANIFEST = 128 * 1024
MAX_IMAGES = 100


class DeliverySnapshotError(ValueError):
    """Frozen evidence is invalid; never fall back to mutable CLI output."""


def _directory(control):
    path = Path(os.path.abspath(control))
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise DeliverySnapshotError('Snapshot directory cannot be a link')
    if not path.is_dir():
        raise DeliverySnapshotError('Snapshot control directory is missing')
    return path


def _identity(control, task_id, round_id, session_id):
    if not isinstance(session_id, str) or not session_id or len(session_id) > 500:
        raise DeliverySnapshotError('Invalid snapshot session identity')
    return dict(control=str(control), task_id=str(UUID(str(task_id))),
                round_id=str(UUID(str(round_id))), session_id=session_id)


def image_metadata(image):
    extensions = dict(FORMATS.values())
    if (not isinstance(image.data, bytes) or not 0 < len(image.data) <= MAX_UPLOAD_BYTES
            or image.content_type not in extensions
            or not isinstance(image.name, str)
            or image.name != safe_name(image.name, extensions[image.content_type])
            or type(image.width) is not int or type(image.height) is not int
            or image.width <= 0 or image.height <= 0
            or image.width * image.height > 89478485
            or hashlib.sha256(image.data).hexdigest() != image.checksum):
        raise DeliverySnapshotError('Invalid validated delivery image metadata')
    return dict(name=image.name, content_type=image.content_type, checksum=image.checksum,
                width=image.width, height=image.height, size=len(image.data))


def _read(path, limit):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
        raise DeliverySnapshotError('Snapshot file is linked or exceeds size limit')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
    with os.fdopen(fd, 'rb') as stream:
        current = os.fstat(stream.fileno())
        if ((current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
                or not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
                or current.st_size > limit):
            raise DeliverySnapshotError('Snapshot file changed while opening')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise DeliverySnapshotError('Snapshot file exceeds size limit')
    return data


def _sync_directory(path):
    if os.name == 'posix':
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _write(path, data):
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def load_delivery(control, task_id, round_id, session_id, expected_count):
    """Return only complete committed evidence; absent commit marker returns None."""
    try:
        root = _directory(control)
        identity = _identity(root, task_id, round_id, session_id)
        manifest = root / MANIFEST
        if not os.path.lexists(manifest):
            return None
        payload = json.loads(_read(manifest, MAX_MANIFEST))
        if (not isinstance(payload, dict) or payload.get('version') != 1
                or payload.get('identity') != identity
                or type(expected_count) is not int or not 0 < expected_count <= MAX_IMAGES
                or not isinstance(payload.get('images'), list)
                or len(payload['images']) != expected_count):
            raise DeliverySnapshotError('Snapshot identity or image count mismatch')
        result, paths = [], set()
        for slot, item in enumerate(payload['images']):
            if (not isinstance(item, dict) or type(item.get('slot')) is not int
                    or item.get('slot') != slot):
                raise DeliverySnapshotError('Invalid snapshot ordering')
            filename = item['file']
            if (not isinstance(filename, str) or len(filename) != 45
                    or not filename.startswith('delivery-') or not filename.endswith('.bin')
                    or any(c not in '0123456789abcdef' for c in filename[9:-4])
                    or filename in paths):
                raise DeliverySnapshotError('Invalid snapshot file path')
            paths.add(filename)
            data = _read(root / filename, MAX_UPLOAD_BYTES)
            image = ValidatedImage(data, item['name'], item['content_type'],
                                   item['checksum'], item['width'], item['height'])
            metadata = image_metadata(image)
            if metadata != {key: item[key] for key in metadata}:
                raise DeliverySnapshotError('Snapshot image metadata mismatch')
            result.append(image)
        return result
    except DeliverySnapshotError:
        raise
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise DeliverySnapshotError('Snapshot is incomplete or corrupt') from exc


def freeze_delivery(control, task_id, round_id, session_id, images):
    """Call only after CLI is stopped and collector has validated every image."""
    root = _directory(control)
    if not 0 < len(images) <= MAX_IMAGES:
        raise DeliverySnapshotError('Invalid delivery image count')
    metadata = [image_metadata(image) for image in images]
    existing = load_delivery(root, task_id, round_id, session_id, len(images))
    if existing is not None:
        if existing != images:
            raise DeliverySnapshotError('Frozen delivery cannot be replaced')
        _sync_directory(root)
        return
    entries = []
    for slot, (image, meta) in enumerate(zip(images, metadata)):
        filename = f'delivery-{uuid4().hex}.bin'
        _write(root / filename, image.data)
        entries.append(dict(meta, slot=slot, file=filename))
    payload = dict(version=1, identity=_identity(root, task_id, round_id, session_id), images=entries)
    temporary = root / f'delivery-{uuid4().hex}.tmp'
    _write(temporary, json.dumps(payload, ensure_ascii=True).encode())
    _sync_directory(root)
    os.replace(temporary, root / MANIFEST)
    _sync_directory(root)
