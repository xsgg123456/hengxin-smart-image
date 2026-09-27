"""Reproduce successful final deliveries preceded by CLI websocket reconnects."""
import json

import pytest

from app.execution.events import parse_events
from app.execution.final_delivery import _final_text
from app.execution.output_collector import OutputCollectionError

NOTICE = {'type': 'error', 'message': 'Reconnecting... 2/5 (stream disconnected before completion: websocket closed by server before response.completed)'}
START = {'type': 'thread.started', 'thread_id': 'same-session'}
FINAL = {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '![01](/work/output/01.jpg)'}}
DONE = {'type': 'turn.completed', 'usage': {'input_tokens': 12}}


def stream(tmp_path, rows):
    path = tmp_path / 'events.jsonl'
    path.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')
    return path


def test_reconnect_then_success_in_same_session(tmp_path):
    path = stream(tmp_path, [START, NOTICE, NOTICE, FINAL, DONE])
    summary = parse_events(path, 'same-session')
    assert summary.error is None and summary.turn_completed
    assert summary.usage == {'input_tokens': 12}
    assert _final_text(path, 'same-session') == FINAL['item']['text']


@pytest.mark.parametrize('rows', [
    [START, NOTICE],
    [START, {'type': 'turn.failed'}],
    [START, {'type': 'thread.started', 'thread_id': 'other'}, NOTICE, FINAL, DONE],
    [START, ['malformed'], NOTICE, FINAL, DONE],
])
def test_reconnect_cannot_hide_failure(tmp_path, rows):
    path = stream(tmp_path, rows)
    assert parse_events(path, 'same-session').error
    with pytest.raises(OutputCollectionError):
        _final_text(path, 'same-session')


@pytest.mark.parametrize('rows', [
    [START, NOTICE, {'type': 'turn.failed'}, FINAL, DONE],
    [START, {'type': 'error', 'message': 'quota exceeded'}, FINAL, DONE],
    [START, FINAL, DONE, NOTICE],
    [START, {'type': 'error', 'message': 'Reconnecting... unexpected'}, FINAL, DONE],
    [START, {'type': 'error', 'message': 'Connection reset without closing handshake'}, FINAL, DONE],
    [START, FINAL, DONE, DONE],
    [START, FINAL, dict(DONE, usage={'input_tokens': 12, 'cached_input_tokens': None})],
])
def test_trust_completed_delivery_over_diagnostics(tmp_path, rows):
    path = stream(tmp_path, rows)
    summary = parse_events(path, 'same-session')
    assert summary.error is None and summary.turn_completed
    assert summary.usage == {'input_tokens': 12}
    assert _final_text(path, 'same-session') == FINAL['item']['text']


@pytest.mark.parametrize('tail', [
    [{'type': 'turn.started'}],
    [{'type': 'item.started', 'item': {'type': 'command_execution'}}],
    [FINAL],
    [{'type': 'turn.started'}, {'type': 'turn.failed'}],
])
def test_earlier_completion_cannot_hide_unfinished_tail(tmp_path, tail):
    path = stream(tmp_path, [START, FINAL, DONE, *tail])
    assert not parse_events(path).turn_completed
    with pytest.raises(OutputCollectionError, match='final_delivery_uncertain|turn_failed'):
        _final_text(path, 'same-session')


@pytest.mark.parametrize('rows', [[FINAL, DONE], [FINAL, START, DONE]])
def test_expected_session_cannot_create_ownership_evidence(tmp_path, rows):
    path = stream(tmp_path, rows)
    with pytest.raises(OutputCollectionError, match='final_delivery_uncertain|final_reply_missing'):
        _final_text(path, 'same-session')


def test_known_usage_survives_later_malformed_accounting(tmp_path):
    path = stream(tmp_path, [START,
        {'type': 'turn.completed', 'turn_id': 'a', 'usage': {'input_tokens': 9}},
        {'type': 'turn.started', 'turn_id': 'b'}, FINAL,
        {'type': 'turn.completed', 'turn_id': 'b', 'usage': {'input_tokens': None}},
    ])
    summary = parse_events(path)
    assert summary.usage == {'input_tokens': 9}
    assert summary.usage_error == 'invalid_usage'
    assert _final_text(path, 'same-session') == FINAL['item']['text']


def test_duplicate_json_keys_are_corruption(tmp_path):
    path = stream(tmp_path, [START, FINAL, DONE])
    with path.open('a', encoding='utf-8') as output:
        output.write('\n{"type":"error","type":"turn.completed"}')
    with pytest.raises(OutputCollectionError, match='invalid_event_stream'):
        _final_text(path, 'same-session')


def test_failed_terminal_is_not_downgraded_by_later_diagnostic(tmp_path):
    path = stream(tmp_path, [START, FINAL, {'type': 'turn.failed'}, NOTICE])
    assert parse_events(path).error == 'turn_failed'
    with pytest.raises(OutputCollectionError, match='turn_failed'):
        _final_text(path, 'same-session')


def test_explicit_stale_completion_cannot_finish_new_turn(tmp_path):
    done = dict(DONE, turn_id='old')
    path = stream(tmp_path, [START, {'type': 'turn.started', 'turn_id': 'old'},
                            FINAL, done, {'type': 'turn.started', 'turn_id': 'new'}, done])
    with pytest.raises(OutputCollectionError, match='invalid_turn_id'):
        _final_text(path, 'same-session')
