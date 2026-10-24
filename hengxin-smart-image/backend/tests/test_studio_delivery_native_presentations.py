"""Final native presentation selection, including historical redisplay."""
import base64
import hashlib
import json
import pytest
from app.overseas.studio import native_images as native
from test_studio_native_images import SESSION, PNG, ENCODED, PREFIX, event, turn, write


def test_confirmation_final_candidate_is_bound_by_completion_receipt(tmp_path):
    rows = turn()
    rows.insert(1, event('item_completed', turn_id='turn-1', thread_id=SESSION,
        item=dict(type='AgentMessage', phase='final_answer', id='call_confirmation',
                  delivery={'kind': 'question'}, questions=[{'id': 'choice'}],
                  content=[{'type': 'Text', 'text': '先选一下尺寸'}])))
    rows[-2]['payload']['item']['id'] = 'msg_actual_final'
    rows.insert(-1, {'type': 'event_msg', 'payload': {'type': 'unknown_incremental', 'extra': True}})
    rows[-1]['payload']['future_metadata'] = {'optional': True}
    write(tmp_path, rows)
    result = native.read_current(tmp_path, SESSION, {}, '完成')
    assert len(result) == 1 and result[0]['cli_turn_id'] == 'turn-1'


def test_completion_selects_matching_final_candidate_without_tool_name_assumptions(tmp_path):
    rows = turn()
    rows.insert(-1, event('item_completed', turn_id='turn-1', thread_id=SESSION,
        item=dict(type='AgentMessage', phase='final_answer', id='unknown_public_event',
                  content=[{'type': 'Text', 'text': '另一个中途消息'}])))
    write(tmp_path, rows)
    assert len(native.read_current(tmp_path, SESSION, {}, '完成')) == 1


@pytest.mark.parametrize('status', ['failed', 'cancelled', 'canceled', 'aborted', 'running', 'unknown'])
def test_explicit_non_success_status_does_not_become_completion(tmp_path, status):
    rows = turn()
    rows[-1]['payload']['status'] = status
    write(tmp_path, rows)
    with pytest.raises(ValueError):
        native.read_current(tmp_path, SESSION, {}, '完成')


def test_end_cursor_prevents_later_turns_and_trailing_damage_from_being_read(tmp_path):
    path = write(tmp_path, turn())
    end = native.snapshot(tmp_path, SESSION)
    write(tmp_path, turn('turn-2', 'later.png'), append=True)
    with path.open('ab') as stream:
        stream.write(b'truncated later record')
    assert native.read_current(tmp_path, SESSION, {}, '完成', end)[0]['path'] == PREFIX + 'exec-1.png'
    assert native.read_history(tmp_path, SESSION, {PREFIX + 'exec-1.png', PREFIX + 'later.png'}, end) == {
        PREFIX + 'exec-1.png': hashlib.sha256(PNG).hexdigest()}


def test_end_cursor_cannot_cut_off_completion_or_change_identity(tmp_path):
    write(tmp_path, turn()[:-1])
    end = native.snapshot(tmp_path, SESSION)
    write(tmp_path, turn()[-1:], append=True)
    with pytest.raises(ValueError, match='Truncated native turn'):
        native.read_current(tmp_path, SESSION, {}, '完成', end)
    with pytest.raises(ValueError, match='identity'):
        native.read_current(tmp_path, SESSION, {}, '完成', dict(end, ino=-1))


def test_current_turn_stops_at_its_completion_without_a_persisted_end(tmp_path):
    write(tmp_path, turn() + turn('turn-2', 'later.png', final='不同的后续回复'))
    assert native.read_current(tmp_path, SESSION, {}, '完成')[0]['cli_turn_id'] == 'turn-1'
    with pytest.raises(ValueError, match='final text differs'):
        native.read_current(tmp_path, SESSION, {}, '不同的后续回复')


def generation_and_display(filename, data):
    rows = turn(filename=filename)
    encoded = base64.b64encode(data).decode()
    return json.loads(json.dumps(rows[1:3]).replace(ENCODED, encoded))


def test_single_public_native_image_survives_later_verification_tool(tmp_path):
    rows = turn()
    rows.insert(-2, {'type': 'response_item', 'payload': {
        'type': 'custom_tool_call', 'name': 'exec', 'call_id': 'verify'}})
    rows.insert(-2, {'type': 'response_item', 'payload': {
        'type': 'custom_tool_call_output', 'call_id': 'verify', 'output': []}})
    write(tmp_path, rows)
    assert native.read_current(tmp_path, SESSION, {}, '完成')[0]['path'] == PREFIX + 'exec-1.png'


def test_multiple_native_generations_use_only_terminal_presentation_batch(tmp_path):
    rows = turn()
    rows[-2:-2] = generation_and_display('last.png', PNG + b'last')
    write(tmp_path, rows)
    assert [item['path'] for item in native.read_current(tmp_path, SESSION, {}, '完成')] == [PREFIX + 'last.png']


def test_later_non_image_tool_does_not_discard_last_presentation_batch(tmp_path):
    rows = turn()
    rows[-2:-2] = generation_and_display('process.png', PNG + b'process')
    rows.insert(-2, {'type': 'response_item', 'payload': {
        'type': 'custom_tool_call', 'name': 'exec', 'call_id': 'more_work'}})
    write(tmp_path, rows)
    assert [item['path'] for item in native.read_current(tmp_path, SESSION, {}, '完成')] == [PREFIX + 'process.png']


def test_single_unpresented_generation_never_becomes_native_delivery(tmp_path):
    write(tmp_path, turn(displayed=False))
    assert native.read_current(tmp_path, SESSION, {}, '完成') == []


def test_identical_pixels_in_two_generated_paths_are_one_native_presentation(tmp_path):
    rows = turn()
    rows[-2:-2] = generation_and_display('same-pixels.png', PNG)
    write(tmp_path, rows)
    result = native.read_current(tmp_path, SESSION, {}, '完成')
    assert len(result) == 1 and result[0]['path'] == PREFIX + 'same-pixels.png'


def test_native_final_batch_preserves_actual_display_order(tmp_path):
    rows = turn()
    extra = generation_and_display('second.png', PNG + b'second')
    rows.insert(2, extra[0])
    rows[3]['payload']['output'].insert(0, extra[1]['payload']['output'][0])
    write(tmp_path, rows)
    assert [item['path'] for item in native.read_current(tmp_path, SESSION, {}, '完成')] == [
        PREFIX + 'second.png', PREFIX + 'exec-1.png']


@pytest.mark.parametrize('previously_displayed', [True, False])
def test_native_redisplay_uses_prior_generation_without_new_generation(tmp_path, previously_displayed):
    write(tmp_path, turn(displayed=previously_displayed))
    cursor = native.snapshot(tmp_path, SESSION)
    current = turn('turn-2', final='')
    del current[1]  # The second invocation displays the existing bytes only.
    write(tmp_path, current, append=True)
    assert native.read_current(tmp_path, SESSION, cursor, '') == [{
        'path': PREFIX + 'exec-1.png', 'checksum': hashlib.sha256(PNG).hexdigest(),
        'cli_turn_id': 'turn-2'}]


def test_native_redisplay_does_not_collect_other_unshown_historical_images(tmp_path):
    previous = turn()
    previous[-2:-2] = generation_and_display('unshown-today.png', PNG + b'other')
    write(tmp_path, previous)
    cursor = native.snapshot(tmp_path, SESSION)
    current = turn('turn-2')
    del current[1]
    write(tmp_path, current, append=True)
    result = native.read_current(tmp_path, SESSION, cursor, '完成')
    assert [item['path'] for item in result] == [PREFIX + 'exec-1.png']


def test_unresolved_tool_display_does_not_invent_an_output(tmp_path):
    rows = turn()
    del rows[1]
    write(tmp_path, rows)
    assert native.read_current(tmp_path, SESSION, {}, '完成') == []


def test_historical_final_batch_does_not_include_new_process_generation(tmp_path):
    write(tmp_path, turn())
    cursor = native.snapshot(tmp_path, SESSION)
    current = turn('turn-2')
    new = generation_and_display('process.png', PNG + b'process')
    for row in new:
        payload = row['payload']
        if 'turn_id' in payload:
            payload['turn_id'] = 'turn-2'
        if 'internal_chat_message_metadata_passthrough' in payload:
            payload['internal_chat_message_metadata_passthrough']['turn_id'] = 'turn-2'
    current[1:2] = new
    write(tmp_path, current, append=True)
    assert [item['path'] for item in native.read_current(tmp_path, SESSION, cursor, '完成')] == [PREFIX + 'exec-1.png']


@pytest.mark.parametrize('prior_end', ['failed', 'interrupted', 'bad-unrelated-image'])
def test_current_native_redisplay_does_not_depend_on_prior_turn_success(tmp_path, prior_end):
    prior = turn()
    if prior_end == 'failed':
        prior[-1] = event('task_failed', turn_id='turn-1')
    elif prior_end == 'interrupted':
        prior = prior[:-2]
    else:
        damaged = generation_and_display('bad.png', PNG + b'bad')[0]
        damaged['payload']['item']['result'] = 'not base64'
        prior.insert(2, damaged)
    write(tmp_path, prior)
    cursor = native.snapshot(tmp_path, SESSION)
    current = turn('turn-2')
    del current[1]
    write(tmp_path, current, append=True)
    assert [item['path'] for item in native.read_current(tmp_path, SESSION, cursor, '完成')] == [PREFIX + 'exec-1.png']


@pytest.mark.parametrize('failure', ['tool', 'diagnostic'])
def test_recovered_tool_or_diagnostic_error_does_not_veto_current_final(tmp_path, failure):
    rows = turn()
    if failure == 'tool':
        previous = event('item_completed', turn_id='turn-1', thread_id=SESSION, item={
            'type': 'Extension', 'kind': 'image_gen.generation', 'status': 'failed',
            'failure': {'message': 'temporary service error'}})
    else:
        previous = event('error', turn_id='turn-1', message='temporary transport error')
    rows.insert(1, previous)
    write(tmp_path, rows)
    assert [item['path'] for item in native.read_current(tmp_path, SESSION, {}, '完成')] == [PREFIX + 'exec-1.png']


def test_diagnostic_without_later_completion_is_not_success(tmp_path):
    rows = turn()[:-1] + [event('error', turn_id='turn-1', message='transport error')]
    write(tmp_path, rows)
    with pytest.raises(ValueError, match='Truncated'):
        native.read_current(tmp_path, SESSION, {}, '完成')
