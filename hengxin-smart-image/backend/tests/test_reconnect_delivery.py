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
    [START, NOTICE, {'type': 'turn.failed'}, FINAL, DONE],
    [START, {'type': 'error', 'message': 'quota exceeded'}, NOTICE, FINAL, DONE],
    [START, FINAL, DONE, NOTICE],
    [START, {'type': 'error', 'message': 'Reconnecting... unexpected'}, FINAL, DONE],
    [START, {'type': 'thread.started', 'thread_id': 'other'}, NOTICE, FINAL, DONE],
    [START, ['malformed'], NOTICE, FINAL, DONE],
])
def test_reconnect_cannot_hide_failure(tmp_path, rows):
    path = stream(tmp_path, rows)
    assert parse_events(path, 'same-session').error
    with pytest.raises(OutputCollectionError):
        _final_text(path, 'same-session')
