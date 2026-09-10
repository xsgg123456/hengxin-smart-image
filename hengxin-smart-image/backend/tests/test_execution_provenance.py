"""Synthetic native-log fixtures test validation, not external model execution."""

import base64
import hashlib
import json
import os

import pytest

from app.execution.output_collector import OutputCollectionError
from app.execution.provenance import ProvenanceError, snapshot_provenance, verify_provenance
from app.modules.files.validation import ValidatedImage


def image(data=b'synthetic-image-bytes'):
    return ValidatedImage(data, 'exec-call1.png', 'image/png',
                          hashlib.sha256(data).hexdigest(), 1, 1)


def generation(output=None, **overrides):
    output = output or image()
    payload = {
        'type': 'item_completed', 'thread_id': 'sid', 'turn_id': 'turn1',
        'item': {'type': 'Extension', 'kind': 'image_gen.generation',
                 'id': 'exec-call1', 'status': 'completed', 'failure': None,
                 'result': base64.b64encode(output.data).decode(),
                 'savedPath': '/home/runner/.codex/generated_images/sid/exec-call1.png'},
    }
    payload.update(overrides)
    return payload


def log(home, *payloads, mode='a', sid='sid'):
    path = home / 'sessions' / '2026' / '09' / '10' / f'rollout-date-{sid}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode, encoding='utf-8') as stream:
        for payload in payloads:
            stream.write(json.dumps({'type': 'event_msg', 'ordinal': 33,
                                     'payload': payload}) + '\n')
    return path


def start(turn='turn1'):
    return {'type': 'task_started', 'turn_id': turn}


def test_new_event_binds_image_and_duplicate_is_idempotent(tmp_path):
    log(tmp_path, start('old'), generation(turn_id='old'))
    baseline = snapshot_provenance(tmp_path)
    log(tmp_path, start(), generation(), generation(),
        {'type': 'task_complete', 'turn_id': 'turn1'})
    verify_provenance(tmp_path, 'sid', baseline, [image()])


@pytest.mark.parametrize('payloads', [
    [], [start()], [{'type': 'agent_message', 'message': 'image_gen.generation completed'}],
    [start(), {'type': 'image_generation_call', 'status': 'completed'}],
])
def test_copy_without_native_event_rejected(tmp_path, payloads):
    log(tmp_path, start('old'), generation(turn_id='old'))
    baseline = snapshot_provenance(tmp_path)
    log(tmp_path, *payloads)
    with pytest.raises(ProvenanceError, match='provenance_missing'):
        verify_provenance(tmp_path, 'sid', baseline, [image()])


@pytest.mark.parametrize('overrides', [{'thread_id': 'other'}, {'turn_id': 'old'}])
def test_wrong_session_or_turn_rejected(tmp_path, overrides):
    log(tmp_path, start(), generation(**overrides))
    with pytest.raises(ProvenanceError, match='session_or_turn'):
        verify_provenance(tmp_path, 'sid', {}, [image()])


def test_old_turn_start_does_not_authorize_new_event(tmp_path):
    log(tmp_path, start())
    baseline = snapshot_provenance(tmp_path)
    log(tmp_path, generation())
    with pytest.raises(ProvenanceError, match='session_or_turn'):
        verify_provenance(tmp_path, 'sid', baseline, [image()])


def test_event_after_turn_completion_rejected(tmp_path):
    log(tmp_path, start(), {'type': 'task_complete', 'turn_id': 'turn1'}, generation())
    with pytest.raises(ProvenanceError, match='session_or_turn'):
        verify_provenance(tmp_path, 'sid', {}, [image()])


@pytest.mark.parametrize('mutation', ['rewrite', 'truncate', 'delete'])
def test_historical_prefix_immutable(tmp_path, mutation):
    path = log(tmp_path, start('old'))
    baseline = snapshot_provenance(tmp_path)
    if mutation == 'delete':
        path.unlink()
    else:
        path.write_text('' if mutation == 'truncate' else 'x' * path.stat().st_size)
    with pytest.raises(ProvenanceError, match='historical_provenance_changed'):
        verify_provenance(tmp_path, 'sid', baseline, [image()])


@pytest.mark.parametrize('field,value', [
    ('savedPath', '/home/runner/.codex/generated_images/other/exec-call1.png'),
    ('savedPath', '/home/runner/.codex/generated_images/sid/copied.png'),
    ('id', 'exec-other'), ('status', 'failed'), ('failure', 'error'),
    ('result', '%%%invalid%%%'), ('result', ''),
])
def test_invalid_native_item_rejected_without_payload_leak(tmp_path, field, value):
    event = generation()
    event['item'][field] = value
    log(tmp_path, start(), event)
    with pytest.raises(ProvenanceError) as error:
        verify_provenance(tmp_path, 'sid', {}, [image()])
    assert 'synthetic-image' not in str(error.value)
    assert '%%%invalid%%%' not in str(error.value)


def test_content_hash_must_match_collected_image(tmp_path):
    log(tmp_path, start(), generation(image(b'different')))
    with pytest.raises(ProvenanceError, match='provenance_missing'):
        verify_provenance(tmp_path, 'sid', {}, [image()])


def test_conflicting_duplicate_rejected(tmp_path):
    log(tmp_path, start(), generation(), generation(image(b'different')))
    with pytest.raises(ProvenanceError, match='conflicting_generation'):
        verify_provenance(tmp_path, 'sid', {}, [image()])


def test_other_session_log_not_used(tmp_path):
    log(tmp_path, start(), generation(), sid='othersid')
    with pytest.raises(ProvenanceError, match='provenance_missing'):
        verify_provenance(tmp_path, 'sid', {}, [image()])


def test_hardlink_log_rejected(tmp_path):
    path = log(tmp_path, start())
    os.link(path, path.with_name('rollout-hardlink-sid.jsonl'))
    with pytest.raises(ProvenanceError, match='hardlink'):
        snapshot_provenance(tmp_path)


def test_symlink_directory_rejected(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    try:
        (tmp_path / 'sessions').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('OS does not permit symlink creation')
    with pytest.raises(OutputCollectionError, match='link_forbidden'):
        snapshot_provenance(tmp_path)


def test_partial_baseline_line_rejected(tmp_path):
    path = log(tmp_path, start())
    path.write_bytes(path.read_bytes().rstrip(b'\n'))
    with pytest.raises(ProvenanceError, match='incomplete_provenance_baseline'):
        snapshot_provenance(tmp_path)


def test_base64_bound_checked_before_decode(tmp_path, monkeypatch):
    monkeypatch.setattr('app.execution.provenance.MAX_BASE64', 3)
    log(tmp_path, start(), generation())
    with pytest.raises(ProvenanceError, match='invalid_generation_payload'):
        verify_provenance(tmp_path, 'sid', {}, [image()])
