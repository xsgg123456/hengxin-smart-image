import json
import os
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.execution import delivery_snapshot as snapshot
from app.modules.files.validation import validate_image
from files_helpers import image_bytes


@pytest.fixture
def delivery(tmp_path):
    image = validate_image(UploadFile(BytesIO(image_bytes()), filename='final.png'))
    return (tmp_path, uuid4(), uuid4(), 'session-current'), [image]


def test_snapshot_roundtrip_is_immutable(delivery):
    args, images = delivery
    snapshot.freeze_delivery(*args, images)
    assert snapshot.load_delivery(*args, 1) == images
    before = (args[0] / snapshot.MANIFEST).read_bytes()
    snapshot.freeze_delivery(*args, images)
    assert (args[0] / snapshot.MANIFEST).read_bytes() == before


@pytest.mark.parametrize('field', ['task', 'round', 'session', 'count', 'control'])
def test_snapshot_rejects_identity_mismatch(delivery, tmp_path, field):
    import shutil
    args, images = delivery
    snapshot.freeze_delivery(*args, images)
    load_args = [*args, 1]
    if field == 'control':
        other = tmp_path / 'other'
        shutil.copytree(args[0], other, ignore=shutil.ignore_patterns('other'))
        load_args[0] = other
    else:
        index = {'task': 1, 'round': 2, 'session': 3, 'count': 4}[field]
        load_args[index] = 2 if field == 'count' else str(uuid4())
    with pytest.raises(snapshot.DeliverySnapshotError):
        snapshot.load_delivery(*load_args)


def test_partial_write_never_becomes_trusted(delivery, monkeypatch):
    args, images = delivery
    def fail_replace(*_):
        raise OSError('crash before commit marker')
    monkeypatch.setattr(snapshot.os, 'replace', fail_replace)
    with pytest.raises(OSError):
        snapshot.freeze_delivery(*args, images)
    assert snapshot.load_delivery(*args, 1) is None
    assert list(args[0].glob('delivery-*.bin'))


@pytest.mark.parametrize('damage', ['bytes', 'size', 'slot', 'escape', 'missing', 'manifest'])
def test_snapshot_corruption_is_not_absence(delivery, damage):
    args, images = delivery
    snapshot.freeze_delivery(*args, images)
    manifest = args[0] / snapshot.MANIFEST
    data = json.loads(manifest.read_bytes())
    blob = args[0] / data['images'][0]['file']
    if damage == 'bytes':
        blob.write_bytes(b'corrupted')
    elif damage == 'missing':
        blob.unlink()
    elif damage == 'manifest':
        manifest.write_bytes(b'{')
    else:
        key, value = {'size': ('size', 1), 'slot': ('slot', 2),
                      'escape': ('file', '../external.png')}[damage]
        data['images'][0][key] = value
        manifest.write_text(json.dumps(data))
    with pytest.raises(snapshot.DeliverySnapshotError):
        snapshot.load_delivery(*args, 1)


@pytest.mark.parametrize('kind', ['hard', 'symbolic'])
def test_snapshot_link_rejected(delivery, kind):
    args, images = delivery
    snapshot.freeze_delivery(*args, images)
    manifest = json.loads((args[0] / snapshot.MANIFEST).read_bytes())
    blob = args[0] / manifest['images'][0]['file']
    external = args[0] / 'external'
    blob.rename(external)
    try:
        if kind == 'hard':
            os.link(external, blob)
        else:
            blob.symlink_to(external)
    except OSError:
        pytest.skip('Host does not grant link creation')
    with pytest.raises(snapshot.DeliverySnapshotError):
        snapshot.load_delivery(*args, 1)


def test_snapshot_does_not_decode_again(delivery, monkeypatch):
    from PIL import Image
    args, images = delivery
    monkeypatch.setattr(Image, 'open', lambda *_: pytest.fail('unexpected image decode'))
    snapshot.freeze_delivery(*args, images)
    assert snapshot.load_delivery(*args, 1) == images


def test_snapshot_rejects_oversized_file(delivery):
    args, images = delivery
    snapshot.freeze_delivery(*args, images)
    manifest = json.loads((args[0] / snapshot.MANIFEST).read_bytes())
    blob = args[0] / manifest['images'][0]['file']
    with blob.open('wb') as stream:
        stream.truncate(snapshot.MAX_UPLOAD_BYTES + 1)
    with pytest.raises(snapshot.DeliverySnapshotError):
        snapshot.load_delivery(*args, 1)


def test_frozen_delivery_cannot_be_changed(delivery):
    from dataclasses import replace
    args, images = delivery
    snapshot.freeze_delivery(*args, images)
    with pytest.raises(snapshot.DeliverySnapshotError):
        snapshot.freeze_delivery(*args, [replace(images[0], name='changed.png')])
