"""Sanitized production wire shape: two distinct IDs in web_search items."""
import json
import pytest
from app.execution.event_json import decode_event
from app.execution.events import parse_events
from app.execution.diagnostics import _unique_object

SEARCH_ID = 'exec-00000000-1111-2222-3333-444444444444'
SEARCH = ('{"type":"%s","item":{"id":"item_6","type":"web_search",'
          '"id":"' + SEARCH_ID + '","query":"example"}}')


@pytest.mark.parametrize('stage', ['item.started', 'item.updated', 'item.completed'])
def test_search_dual_id_preserves_historical_identity(stage):
    assert decode_event(SEARCH % stage)['item']['id'] == SEARCH_ID
    with pytest.raises(ValueError):
        json.loads(SEARCH % stage, object_pairs_hook=_unique_object)


@pytest.mark.parametrize('raw', [
    '{"type":"thread.started","thread_id":"one","thread_id":"two"}',
    '{"type":"turn.completed","type":"item.started"}',
    '{"type":"turn.completed","usage":{"input_tokens":1,"input_tokens":2}}',
    (SEARCH % 'item.completed').replace('web_search', 'agent_message'),
    (SEARCH % 'item.completed').replace('item_6', 'untrusted'),
    (SEARCH % 'item.completed').replace(SEARCH_ID, 'exec-invalid'),
    (SEARCH % 'item.completed').replace('"query":"example"', '"id":"extra"'),
    (SEARCH % 'item.completed').replace('"query":"example"', '"query":"a","query":"b"'),
    (SEARCH % 'item.completed').replace('"query":"example"', '"action":{"id":1,"id":2}'),
    (SEARCH % 'turn.completed'),
    '[]',
])
def test_other_duplicates_and_invalid_shapes_stay_rejected(raw):
    with pytest.raises(ValueError):
        decode_event(raw)


def wire(tail=None):
    rows = ['{"type":"thread.started","thread_id":"session-123"}',
            '{"type":"turn.started"}', SEARCH % 'item.started', SEARCH % 'item.completed',
            '{"type":"item.completed","item":{"type":"command_execution","status":"failed"}}',
            '{"type":"item.completed","item":{"id":"answer","type":"agent_message","text":"完整最终回复"}}']
    return '\n'.join(rows + (tail if tail is not None else ['{"type":"turn.completed"}'])) + '\n'


def test_completed_after_search_and_recovered_tool_error(tmp_path):
    path = tmp_path / 'events.jsonl'
    path.write_text(wire(), encoding='utf-8')
    summary = parse_events(path)
    assert summary.error is None and summary.turn_completed
    assert summary.final_text == '完整最终回复'
    assert parse_events(path, 'different-session').error == 'session_mismatch'


@pytest.mark.parametrize('tail', [[], ['{"type":"turn.failed"}']])
def test_no_completion_is_not_success(tmp_path, tail):
    path = tmp_path / 'events.jsonl'
    path.write_text(wire(tail), encoding='utf-8')
    assert not parse_events(path).turn_completed
