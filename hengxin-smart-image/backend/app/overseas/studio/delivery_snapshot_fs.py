"""Validation and bounded IO for backend-owned Studio delivery receipts."""
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from uuid import NAMESPACE_URL, uuid5

from app.overseas.upload_limits import MAX_UPLOAD_BYTES
from . import context_fs as fs
from .native_images import MAX_IMAGES
from .output_files import validated

MAX_MANIFEST_BYTES = 32 * 1024 * 1024
IDENTITY_KEYS = {'jobId', 'taskId', 'turnId', 'conversationId', 'sessionId'}
META_KEYS = {'pictureId', 'checksum', 'sizeBytes', 'name', 'contentType', 'width', 'height'}


def canonical_target(target):
    """Canonicalize a reference, never use it as a private filesystem path."""
    if not isinstance(target, str):
        raise ValueError('Invalid delivery target')
    value = target.removeprefix('sandbox:')
    if (not value or value.startswith('//') or value.endswith('/')
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or any(c in value for c in '\\:?#')
            or any(p in ('.', '..') for p in value.split('/'))):
        raise ValueError('Invalid delivery target')
    logical = PurePosixPath(value)
    return str(logical if logical.is_absolute() else PurePosixPath('/work') / logical)


def identity_value(identity, session_id):
    if not isinstance(identity, dict) or not isinstance(session_id, str) or not session_id:
        raise ValueError('Invalid delivery identity')
    result = dict(identity)
    if 'sessionId' in result and result['sessionId'] != session_id:
        raise ValueError('Delivery session identity mismatch')
    result['sessionId'] = session_id
    if (set(result) != IDENTITY_KEYS
            or any(not isinstance(v, str) or not v for v in result.values())):
        raise ValueError('Invalid delivery identity')
    return result


def picture_id(identity, target):
    key = json.dumps([identity['jobId'], canonical_target(target)], separators=(',', ':'))
    return str(uuid5(NAMESPACE_URL, 'hengxin:studio:delivery:' + key))


def metadata(identity, target, image):
    return dict(pictureId=picture_id(identity, target), checksum=image.checksum,
                sizeBytes=len(image.data), name=image.name, contentType=image.content_type,
                width=image.width, height=image.height)


def check_image(image):
    if not isinstance(image.data, bytes):
        raise ValueError('Invalid delivery file')
    checked = validated(image.data, image.name, image.content_type)
    if checked != image:
        raise ValueError('Delivery image metadata mismatch')
    return checked


def check_manifest(value):
    if (not isinstance(value, dict)
            or set(value) != {'version', 'identity', 'finalText', 'targets', 'ready', 'items'}
            or type(value['version']) is not int or value['version'] != 1
            or not isinstance(value['finalText'], str)
            or type(value['ready']) is not bool
            or not isinstance(value['identity'], dict)):
        raise ValueError('Invalid delivery manifest')
    identity_value(value['identity'], value['identity'].get('sessionId'))
    targets, items = value['targets'], value['items']
    if (not isinstance(targets, list) or not isinstance(items, list)
            or len(targets) > MAX_IMAGES or len(items) != len(targets)
            or len({canonical_target(t) for t in targets}) != len(targets)):
        raise ValueError('Invalid delivery target list')
    for order, (target, row) in enumerate(zip(targets, items, strict=True)):
        if (not isinstance(row, dict) or row.get('target') != target
                or type(row.get('order')) is not int or row['order'] != order
                or row.get('snapshot') != f'snapshots/{order:04d}.bin'
                or row.get('status') not in ('pending', 'capturing', 'captured')):
            raise ValueError('Invalid delivery item')
        expected = {'target', 'order', 'snapshot', 'status'}
        if row['status'] != 'pending':
            expected |= META_KEYS
            if (row.get('pictureId') != picture_id(value['identity'], target)
                    or not isinstance(row.get('checksum'), str)
                    or not re.fullmatch('[0-9a-f]{64}', row['checksum'])
                    or type(row.get('sizeBytes')) is not int
                    or not 0 <= row['sizeBytes'] <= MAX_UPLOAD_BYTES
                    or not (all(row.get(k) is None for k in ('width', 'height')) or
                        all(type(row.get(k)) is int and row[k] > 0 for k in ('width', 'height')))
                    or not isinstance(row.get('name'), str) or not row['name']
                    or not isinstance(row.get('contentType'), str) or not row['contentType']):
                raise ValueError('Invalid delivery file metadata')
        if set(row) != expected:
            raise ValueError('Invalid delivery item fields')
    if value['ready'] != all(row['status'] == 'captured' for row in items):
        raise ValueError('Invalid delivery readiness')
    return value


def read_bytes(path, limit):
    with fs.reader(path) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Delivery snapshot exceeds resource limit')
    return data


def read_manifest(root):
    path = fs.checked(root / 'manifest.json', missing=True, directory=False)
    if not path.exists():
        return None
    return check_manifest(json.loads(read_bytes(path, MAX_MANIFEST_BYTES)))


def save_manifest(root, manifest):
    check_manifest(manifest)
    data = json.dumps(manifest, ensure_ascii=False, separators=(',', ':'),
                      sort_keys=True, allow_nan=False).encode('utf-8')
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError('Delivery manifest exceeds resource limit')
    fs.write(root / 'manifest.json', data)


def snapshot_path(root, row):
    # The path is derived from checked order, not from model-controlled targets.
    expected = f"snapshots/{row['order']:04d}.bin"
    if row['snapshot'] != expected:
        raise ValueError('Invalid delivery snapshot path')
    return fs.checked(root / expected, missing=True, directory=False)


def read_image(root, row):
    data = read_bytes(snapshot_path(root, row), MAX_UPLOAD_BYTES)
    if len(data) != row['sizeBytes'] or hashlib.sha256(data).hexdigest() != row['checksum']:
        raise ValueError('Delivery snapshot checksum mismatch')
    image = validated(data, row['name'], row['contentType'])
    if (image.name != row['name'] or image.width != row['width']
            or image.height != row['height']):
        raise ValueError('Delivery snapshot metadata mismatch')
    return image


def root_path(control, *, create=False):
    root = fs.checked(Path(control), missing=True, directory=True)
    if create:
        root = fs.mkdir(root)
        fs.sync(root.parent)
    return root
