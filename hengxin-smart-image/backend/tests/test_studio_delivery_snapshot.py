"""Fault injection at durable receipt boundaries; no model or production services."""
import json
import os
from dataclasses import replace
from io import BytesIO
from uuid import UUID

import pytest
from PIL import Image

from app.overseas.studio import context_fs as fs
from app.overseas.studio import delivery_snapshot as snapshot
from app.overseas.studio.delivery_snapshot_fs import validated


IDENTITY = dict(jobId='job-1', taskId='task-1', turnId='turn-1', conversationId='conversation-1')
TARGETS = ['/work/图二.png', 'sandbox:/work/图一.png']
REPLY = '先看这两张图片。\n![二](/work/图二.png)\n![一](sandbox:/work/图一.png)'


@pytest.fixture
def control(tmp_path):
    return tmp_path / 'control' / 'delivery'


def picture(color='red', name='image.png'):
    stream = BytesIO()
    Image.new('RGB', (3, 2), color).save(stream, format='PNG')
    return validated(stream.getvalue(), name)


def begin(control, targets=None):
    return snapshot.begin(control, IDENTITY, REPLY, 'session-1', TARGETS if targets is None else targets)


def test_order_identity_bytes_and_idempotence(control):
    first, second = picture('red', '二.png'), picture('blue', '一.png')
    pending = begin(control)
    assert not pending['ready']
    assert all(row['status'] == 'pending' and 'pictureId' not in row for row in pending['items'])
    snapshot.capture(control, TARGETS[1], second)
    partial = snapshot.load(control)
    assert [row['status'] for row in partial['items']] == ['pending', 'captured']
    assert list(snapshot.images(control, captured_only=True))[0][1] == second
    with pytest.raises(ValueError, match='incomplete'):
        list(snapshot.images(control))
    done = snapshot.capture(control, TARGETS[0], first)
    assert done['ready']
    assert begin(control) == done == snapshot.load(control)
    actual = list(snapshot.images(control, pending))
    assert [(target, image) for target, image, _ in actual] == list(zip(TARGETS, [first, second]))
    assert [row['order'] for _, _, row in actual] == [0, 1]
    assert all(UUID(row['pictureId']).version == 5 for _, _, row in actual)
    assert snapshot.capture(control, TARGETS[0], first) == done
    assert done['identity'] == dict(IDENTITY, sessionId='session-1') and done['finalText'] == REPLY
    assert all('data' not in row for row in done['items'])


def test_no_images_is_complete_and_load_does_not_create(control):
    assert snapshot.load(control) is None and not control.exists()
    assert begin(control, [])['ready']
    assert list(snapshot.images(control)) == []


@pytest.mark.parametrize('field,value', [('jobId', 'job-2'), ('turnId', 'turn-2'),
                                      ('taskId', 'task-2'), ('conversationId', 'conversation-2')])
def test_identity_mismatch_keeps_original(control, field, value):
    original = begin(control)
    with pytest.raises(ValueError, match='mismatch'):
        snapshot.begin(control, {**IDENTITY, field: value}, REPLY, 'session-1', TARGETS)
    assert snapshot.load(control) == original


@pytest.mark.parametrize('reply,session,targets', [('changed', 'session-1', TARGETS),
                                                  (REPLY, 'session-2', TARGETS),
                                                  (REPLY, 'session-1', TARGETS[::-1])])
def test_final_evidence_is_immutable(control, reply, session, targets):
    original = begin(control)
    with pytest.raises(ValueError, match='mismatch'):
        snapshot.begin(control, IDENTITY, reply, session, targets)
    assert snapshot.load(control) == original


def test_new_bytes_at_same_source_cannot_replace_frozen_image(control):
    begin(control)
    first = picture()
    frozen = snapshot.capture(control, TARGETS[0], first)
    with pytest.raises(ValueError, match='immutable'):
        snapshot.capture(control, TARGETS[0], picture('blue'))
    assert snapshot.load(control) == frozen
    assert list(snapshot.images(control, captured_only=True))[0][1].data == first.data


def test_picture_id_depends_on_job_and_canonical_target_not_bytes(control, tmp_path):
    begin(control, ['image.png'])
    a = snapshot.capture(control, '/work/image.png', picture())['items'][0]
    other = tmp_path / 'other'
    snapshot.begin(other, IDENTITY, 'different reply', 'session-1', ['sandbox:/work/image.png'])
    b = snapshot.capture(other, 'image.png', picture('blue'))['items'][0]
    assert a['pictureId'] == b['pictureId'] and a['checksum'] != b['checksum']
    third = tmp_path / 'third'
    snapshot.begin(third, {**IDENTITY, 'jobId': 'job-2'}, REPLY, 'session-1', ['image.png'])
    c = snapshot.capture(third, 'image.png', picture())['items'][0]
    assert c['pictureId'] != a['pictureId']


@pytest.mark.parametrize('after', [False, True])
def test_begin_replace_failure_is_reentrant(control, monkeypatch, after):
    real = os.replace
    def fail(source, target):
        if after:
            real(source, target)
        raise OSError('simulated process failure')
    with monkeypatch.context() as patch:
        patch.setattr(fs.os, 'replace', fail)
        with pytest.raises(OSError):
            begin(control)
    assert begin(control) == snapshot.load(control)


@pytest.mark.parametrize('stage', [1, 2, 3])
@pytest.mark.parametrize('after', [False, True])
def test_capture_survives_each_atomic_replace_boundary(control, monkeypatch, stage, after):
    begin(control)
    first, second = picture(), picture('blue')
    snapshot.capture(control, TARGETS[0], first)
    real, calls = os.replace, 0
    def fail(source, target):
        nonlocal calls
        calls += 1
        if calls == stage:
            if after:
                real(source, target)
            raise OSError('simulated process failure')
        return real(source, target)
    with monkeypatch.context() as patch:
        patch.setattr(fs.os, 'replace', fail)
        with pytest.raises(OSError):
            snapshot.capture(control, TARGETS[1], second)
    recovered = snapshot.load(control)
    assert list(snapshot.images(control, captured_only=True))[0][1] == first
    assert recovered['ready'] == (stage == 3 or (stage == 2 and after))
    done = snapshot.capture(control, TARGETS[1], second)
    assert done['ready'] and [image for _, image, _ in snapshot.images(control)] == [first, second]
    assert not list(control.rglob('.context-write-*'))


def test_committed_orphan_recovers_without_source_image(control, monkeypatch):
    begin(control, [TARGETS[0]])
    real = os.replace
    def fail_after_snapshot(source, target):
        real(source, target)
        if str(target).endswith('.bin'):
            raise OSError('crash after snapshot rename')
    with monkeypatch.context() as patch:
        patch.setattr(fs.os, 'replace', fail_after_snapshot)
        with pytest.raises(OSError):
            snapshot.capture(control, TARGETS[0], picture())
    with monkeypatch.context() as patch:
        patch.setattr(snapshot, 'capture', lambda *_args: pytest.fail('Source must not be recaptured'))
        assert snapshot.load(control)['ready']
        assert list(snapshot.images(control))[0][1] == picture()


@pytest.mark.parametrize('mutation', ['bytes', 'missing', 'metadata', 'escape'])
def test_corrupt_snapshot_is_explicit_failure(control, mutation):
    begin(control, [TARGETS[0]])
    receipt = snapshot.capture(control, TARGETS[0], picture())
    target = control / receipt['items'][0]['snapshot']
    if mutation == 'bytes':
        target.write_bytes(picture('blue').data)
    elif mutation == 'missing':
        target.unlink()
    else:
        receipt['items'][0]['width' if mutation == 'metadata' else 'snapshot'] = (
            10 if mutation == 'metadata' else '../outside.png')
        (control / 'manifest.json').write_text(json.dumps(receipt), encoding='utf-8')
    with pytest.raises((ValueError, OSError)):
        list(snapshot.images(control, captured_only=True))


@pytest.mark.parametrize('target', ['../x.png', '/work/a/../x.png', '/work/x.png\x00',
                                    '/work\\x.png', 'https://example.com/x.png'])
def test_target_escape_is_rejected_before_receipt_creation(control, target):
    with pytest.raises(ValueError):
        begin(control, [target])
    assert not control.exists()


@pytest.mark.parametrize('kind', ['root', 'manifest', 'snapshot', 'hardlink'])
def test_filesystem_links_are_rejected(control, tmp_path, kind):
    outside = tmp_path / 'outside'
    outside.mkdir()
    if kind == 'root':
        control.parent.mkdir()
        try:
            control.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip('Symlink creation unavailable')
        with pytest.raises(ValueError):
            begin(control)
        assert not list(outside.iterdir())
        return
    begin(control, [TARGETS[0]])
    receipt = snapshot.capture(control, TARGETS[0], picture())
    path = control / ('manifest.json' if kind == 'manifest' else receipt['items'][0]['snapshot'])
    other = outside / path.name
    path.replace(other)
    try:
        os.link(other, path) if kind == 'hardlink' else path.symlink_to(other)
    except OSError:
        pytest.skip('Link creation unavailable')
    with pytest.raises(ValueError):
        list(snapshot.images(control))


def test_resource_limits_duplicate_targets_and_untrusted_image_metadata(control):
    for targets in [[f'/work/{n}.png' for n in range(101)], ['x.png', '/work/x.png']]:
        with pytest.raises(ValueError):
            begin(control, targets)
    begin(control, [TARGETS[0]])
    with pytest.raises(ValueError, match='metadata'):
        snapshot.capture(control, TARGETS[0], replace(picture(), checksum='0' * 64))
    assert snapshot.load(control)['items'][0]['status'] == 'pending'


def test_fsync_failure_after_rename_recovers(control, monkeypatch):
    begin(control, [TARGETS[0]])
    real = fs.sync
    def fail(path):
        if path.name == 'snapshots':
            raise OSError('directory fsync failed')
        return real(path)
    with monkeypatch.context() as patch:
        patch.setattr(fs, 'sync', fail)
        with pytest.raises(OSError):
            snapshot.capture(control, TARGETS[0], picture())
    assert snapshot.load(control)['ready']
    assert list(snapshot.images(control))[0][1] == picture()


def test_prepared_version_cannot_change_after_failed_byte_write(control, monkeypatch):
    begin(control, [TARGETS[0]])
    real = fs.write
    def fail(path, data):
        if str(path).endswith('.bin'):
            raise OSError('disk full')
        return real(path, data)
    with monkeypatch.context() as patch:
        patch.setattr(fs, 'write', fail)
        with pytest.raises(OSError):
            snapshot.capture(control, TARGETS[0], picture())
    assert snapshot.load(control)['items'][0]['status'] == 'capturing'
    with pytest.raises(ValueError, match='immutable'):
        snapshot.capture(control, TARGETS[0], picture('blue'))
    assert snapshot.capture(control, TARGETS[0], picture())['ready']
