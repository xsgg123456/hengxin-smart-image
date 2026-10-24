"""Studio accepts explicit completion, not a guessed terminal notification."""
import json

import pytest

from app.overseas.studio.completion import read


def success(text='![图片](/work/result.png)', turn_id=None):
    identity = {'turn_id': turn_id} if turn_id else {}
    return [dict(type='thread.started', thread_id='session'),
            dict(type='turn.started', **identity),
            dict(type='item.completed', item={'type': 'agent_message', 'text': text}, **identity),
            dict(type='turn.completed', usage={'input_tokens': 9, 'output_tokens': 3}, **identity)]


def parse(tmp_path, records, expected='session'):
    path = tmp_path / 'events.jsonl'
    path.write_text(''.join(json.dumps(record) + '\n' for record in records), encoding='utf-8')
    return read(path, expected)


@pytest.mark.parametrize('notification', [
    {'type': 'notification.future', 'details': {'status': 'new'}},
    {'type': 'item.text_delta', 'text': '增量'},
    {'type': 'turn.usage_notice', 'extension': True},
])
@pytest.mark.parametrize('position', ['before_completion', 'after_completion'])
def test_unknown_notification_and_incremental_fields_preserve_explicit_completion(tmp_path, notification, position):
    rows = success(turn_id='turn-1')
    for row in rows:
        row['future_field'] = {'ignored': True}
    rows.insert(-1 if position == 'before_completion' else len(rows), notification)
    result = parse(tmp_path, rows)
    assert result.turn_completed and not result.error
    assert result.final_text == '![图片](/work/result.png)'
    assert result.usage == {'input_tokens': 9, 'output_tokens': 3}


@pytest.mark.parametrize('terminal', [
    {'type': 'error', 'message': 'runtime failure'},
    {'type': 'turn.failed'}, {'type': 'turn.aborted'}, {'type': 'turn.cancelled'},
    {'type': 'turn.canceled'}, {'type': 'task.cancelled'},
    {'type': 'notification.future', 'status': 'failed'},
    {'type': 'notification.future', 'error': {'message': 'failed'}},
    {'type': 'notification.future', 'failure': {'message': 'failed'}},
    {'type': 'turn.started', 'turn_id': 'turn-2'},
    {'type': 'item.started', 'item': {'type': 'command_execution'}},
])
def test_new_work_or_failure_after_completion_invalidates_old_success(tmp_path, terminal):
    result = parse(tmp_path, success() + [terminal])
    assert not result.turn_completed and result.final_text is None


def test_temporary_diagnostic_before_success_can_recover(tmp_path):
    rows = success()
    rows.insert(-1, {'type': 'error', 'message': 'transient diagnostic'})
    result = parse(tmp_path, rows)
    assert result.turn_completed and result.final_text and not result.error


@pytest.mark.parametrize('status', ['failed', 'cancelled', 'aborted', 'running', 'new-terminal-status'])
def test_explicit_completion_cannot_hide_failure_or_unknown_status(tmp_path, status):
    rows = success()
    rows[-1]['status'] = status
    result = parse(tmp_path, rows)
    assert not result.turn_completed and result.final_text is None and result.error


@pytest.mark.parametrize('event', [
    {'type': 'turn.ended', 'status': 'unknown'},
    {'type': 'turn.stopped'}, {'type': 'task.finished', 'status': 'success'},
])
def test_unknown_terminal_protocol_does_not_preserve_old_success(tmp_path, event):
    result = parse(tmp_path, success() + [event])
    assert not result.turn_completed and result.error == 'unknown_terminal_event'


def test_intermediate_confirmation_is_not_the_later_final_reply(tmp_path):
    rows = success('请先确认')[:-1]
    rows += [dict(type='item.completed', item={'type': 'tool_call', 'id': 'confirm'}),
             dict(type='item.completed', item={'type': 'agent_message', 'text': '![图](/work/final.jpg)'}),
             dict(type='turn.completed')]
    result = parse(tmp_path, rows)
    assert result.final_text == '![图](/work/final.jpg)' and not result.error


@pytest.mark.parametrize('change', [
    lambda rows: rows[0].update(thread_id='another'),
    lambda rows: rows[-1].update(turn_id='another'),
    lambda rows: rows.insert(-1, {'type': 'notification.future', 'thread_id': 'another'}),
    lambda rows: rows.insert(-1, {'type': 'notification.future', 'turn_id': 'another'}),
])
def test_session_and_turn_identity_stay_strict(tmp_path, change):
    rows = success(turn_id='turn-1')
    change(rows)
    result = parse(tmp_path, rows)
    assert result.error in ('session_mismatch', 'invalid_turn_id')


def test_later_turn_needs_its_own_final_and_completion(tmp_path):
    rows = success(turn_id='first') + [dict(type='turn.started', turn_id='second')]
    result = parse(tmp_path, rows)
    assert not result.turn_completed and result.final_text is None
    rows += success('second final', turn_id='second')[2:]
    result = parse(tmp_path, rows)
    assert result.turn_completed and result.final_text == 'second final' and not result.error


def test_repeated_completion_is_idempotent_and_does_not_revive_failure(tmp_path):
    rows = success(turn_id='turn-1')
    result = parse(tmp_path, rows + [rows[-1]])
    assert result.usage == {'input_tokens': 9, 'output_tokens': 3}
    assert result.final_text
    result = parse(tmp_path, rows + [dict(type='turn.failed'), rows[-1]])
    assert not result.turn_completed and result.error == 'turn_failed'


def test_usage_diagnostic_does_not_discard_success(tmp_path):
    rows = success()
    rows[-1]['usage']['extra_tokens'] = 'unknown'
    result = parse(tmp_path, rows)
    assert result.turn_completed and result.final_text and not result.error
    assert result.usage_error == 'invalid_usage'
    assert result.usage == {'input_tokens': 9, 'output_tokens': 3}


def test_no_completion_record_is_not_inferred_from_images(tmp_path):
    result = parse(tmp_path, success()[:-1])
    assert not result.turn_completed and result.final_text is None


def test_invalid_json_and_missing_stream_fail_closed(tmp_path):
    path = tmp_path / 'events.jsonl'
    assert read(path).error == 'unreadable_event_stream'
    path.write_text('{"type":"turn.completed",', encoding='utf-8')
    assert read(path).error == 'invalid_event_stream'


def test_unknown_notification_alone_cannot_authenticate_a_session_or_success(tmp_path):
    result = parse(tmp_path, [dict(type='notification.future', thread_id='session', status='success')])
    assert result.session_id is None and not result.turn_completed and result.final_text is None


def test_explicit_empty_final_message_can_deliver_native_images(tmp_path):
    result = parse(tmp_path, success(''))
    assert result.turn_completed and result.final_text == '' and not result.error
