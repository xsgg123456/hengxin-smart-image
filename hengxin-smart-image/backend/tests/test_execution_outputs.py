import json
import os

import pytest
from PIL import Image

from app.execution.events import parse_events
from app.execution.output_collector import (
    OutputCollectionError, collect_outputs, snapshot_outputs,
)


def picture(home, name='new.png', color='red'):
    path = home / 'generated_images' / 'session1' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (8, 9), color).save(path)
    return path


def manifest(home, entries):
    path = home / 'generated_images' / 'session1' / 'manifest.json'
    path.write_text(json.dumps({'outputs': entries}), encoding='utf-8')
    return path


def test_single_new_image_never_selects_latest_history(tmp_path):
    picture(tmp_path, 'old.png')
    known = snapshot_outputs(tmp_path, 'session1')
    picture(tmp_path, 'new.png', 'blue')
    outputs = collect_outputs(tmp_path, 'session1', known, 1)
    assert [image.name for image in outputs] == ['new.png']
    assert (outputs[0].width, outputs[0].height) == (8, 9)


@pytest.mark.parametrize('mutation', ['overwrite', 'delete'])
def test_history_must_remain_immutable(tmp_path, mutation):
    old = picture(tmp_path, 'old.png')
    known = snapshot_outputs(tmp_path, 'session1')
    old.unlink() if mutation == 'delete' else old.write_bytes(b'changed')
    picture(tmp_path)
    with pytest.raises(OutputCollectionError, match='historical_output_changed'):
        collect_outputs(tmp_path, 'session1', known, 1)


def test_multi_image_order_is_slot_order_not_creation_order(tmp_path):
    picture(tmp_path, 'a.png')
    picture(tmp_path, 'b.png')
    manifest(tmp_path, [{'slot': 1, 'file': 'a.png'}, {'slot': 0, 'file': 'b.png'}])
    assert [image.name for image in collect_outputs(tmp_path, 'session1', {}, 2)] == [
        'b.png', 'a.png',
    ]


def test_multi_image_without_manifest_rejected(tmp_path):
    picture(tmp_path, 'a.png')
    picture(tmp_path, 'b.png')
    with pytest.raises(OutputCollectionError, match='manifest_required'):
        collect_outputs(tmp_path, 'session1', {}, 2)


@pytest.mark.parametrize('entries', [
    [{'slot': 0, 'file': '../outside.png'}],
    [{'slot': 0, 'file': '/outside.png'}],
    [{'slot': 0, 'file': 'C:\\outside.png'}],
    [{'slot': True, 'file': 'new.png'}],
    [{'slot': 2, 'file': 'new.png'}],
    [{'slot': 0, 'file': 'missing.png'}],
    [{'slot': 0, 'file': 'new.png'}, {'slot': 0, 'file': 'b.png'}],
    [{'slot': 0, 'file': 'new.png'}, {'slot': 1, 'file': 'new.png'}],
])
def test_invalid_manifests_rejected(tmp_path, entries):
    picture(tmp_path)
    manifest(tmp_path, entries)
    with pytest.raises(OutputCollectionError):
        collect_outputs(tmp_path, 'session1', {}, len(entries))


def test_historical_manifest_cannot_be_replayed(tmp_path):
    picture(tmp_path, 'old.png')
    manifest(tmp_path, [{'slot': 0, 'file': 'old.png'}])
    known = snapshot_outputs(tmp_path, 'session1')
    picture(tmp_path)
    with pytest.raises(OutputCollectionError, match='historical_manifest'):
        collect_outputs(tmp_path, 'session1', known, 1)


@pytest.mark.parametrize('kind', ['none', 'corrupt', 'extra', 'history_only'])
def test_no_real_new_exact_image_set_cannot_succeed(tmp_path, kind):
    known = {}
    if kind != 'none':
        path = picture(tmp_path)
        if kind == 'corrupt':
            path.write_bytes(b'not a png')
        elif kind == 'extra':
            picture(tmp_path, 'extra.png')
        else:
            known = snapshot_outputs(tmp_path, 'session1')
    with pytest.raises(OutputCollectionError):
        collect_outputs(tmp_path, 'session1', known, 1)


def test_hardlinks_rejected(tmp_path):
    path = picture(tmp_path)
    os.link(path, path.with_name('linked.png'))
    with pytest.raises(OutputCollectionError, match='hardlink'):
        snapshot_outputs(tmp_path, 'session1')


def test_symlink_escape_rejected(tmp_path):
    path = picture(tmp_path)
    try:
        path.with_name('link.png').symlink_to(path)
    except OSError:
        pytest.skip('OS does not grant symlink creation')
    with pytest.raises(OutputCollectionError, match='link'):
        collect_outputs(tmp_path, 'session1', {}, 1)


@pytest.mark.parametrize('session', ['../other', '/root', 'a/b', 'a\\b', ''])
def test_session_path_traversal_rejected(tmp_path, session):
    with pytest.raises(OutputCollectionError, match='session'):
        snapshot_outputs(tmp_path, session)


def events(tmp_path, rows):
    path = tmp_path / 'events.jsonl'
    path.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')
    return path


@pytest.mark.parametrize('turn_id', [None, 'turn-1'])
def test_completed_event_duplicates_do_not_double_count(tmp_path, turn_id):
    terminal = {'type': 'turn.completed', 'usage': {'input_tokens': 7, 'output_tokens': 3}}
    if turn_id:
        terminal['turn_id'] = turn_id
    result = parse_events(events(tmp_path, [
        {'type': 'thread.started', 'thread_id': 's1'}, terminal, terminal,
    ]))
    assert result.session_id == 's1'
    assert result.usage == {'input_tokens': 7, 'output_tokens': 3}
    assert result.turn_completed and result.error is None


def test_missing_usage_is_unknown(tmp_path):
    result = parse_events(events(tmp_path, [{'type': 'turn.completed'}]))
    assert result.usage is None and result.turn_completed


def test_session_mismatch_fails_and_errors_are_sanitized(tmp_path):
    result = parse_events(events(tmp_path, [
        {'type': 'thread.started', 'thread_id': 'another'},
        {'type': 'turn.completed'},
    ]), 'expected')
    assert result.error == 'session_mismatch'
    result = parse_events(events(tmp_path, [{'type': 'error', 'message': 'secret'}]))
    assert result.error == 'cli_error'


def test_distinct_turn_usage_and_malformed_events(tmp_path):
    path = events(tmp_path, [
        {'type': 'turn.completed', 'turn_id': 'a', 'usage': {'input_tokens': 4}},
        {'type': 'turn.completed', 'turn_id': 'b', 'usage': {'input_tokens': 5}},
    ])
    assert parse_events(path).usage == {'input_tokens': 9}
    with path.open('a') as stream:
        stream.write('\n{invalid')
    assert parse_events(path).error == 'invalid_event_stream'


def test_failure_after_duplicate_terminal_still_fails(tmp_path):
    result = parse_events(events(tmp_path, [
        {'type': 'turn.completed', 'turn_id': 'a'},
        {'type': 'turn.failed', 'turn_id': 'a'},
    ]))
    assert result.error == 'turn_failed'


@pytest.mark.parametrize('usage', [{'input_tokens': -1}, {'input_tokens': True}, []])
def test_invalid_usage_cannot_become_billing_data(tmp_path, usage):
    result = parse_events(events(tmp_path, [{'type': 'turn.completed', 'usage': usage}]))
    assert result.error == 'invalid_usage' and result.usage is None


def test_external_per_round_manifest(tmp_path):
    picture(tmp_path, 'a.png')
    picture(tmp_path, 'b.png')
    path = tmp_path / 'round-manifest.json'
    path.write_text(json.dumps({'outputs': [
        {'slot': 0, 'file': 'b.png'}, {'slot': 1, 'file': 'a.png'},
    ]}), encoding='utf-8')
    images = collect_outputs(tmp_path, 'session1', {}, 2, manifest_path=path)
    assert [image.name for image in images] == ['b.png', 'a.png']
