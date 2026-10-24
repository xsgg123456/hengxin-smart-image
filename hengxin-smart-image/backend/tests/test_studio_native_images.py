import base64
import hashlib
import json
import os

import pytest

from app.overseas.studio import native_images as native
from app.overseas.studio import native_rollout as rollout

SESSION = '4b04db11-7ce7-4ec1-a979-333333333333'
PNG = b'\x89PNG\r\n\x1a\nfixture-image'
ENCODED = base64.b64encode(PNG).decode()
PREFIX = f'/home/runner/.codex/generated_images/{SESSION}/'


def event(kind, **kwargs):
    return {'type': 'event_msg', 'payload': {'type': kind, **kwargs}}


def turn(turn_id='turn-1', filename='exec-1.png', displayed=True, final='完成'):
    rows = [event('task_started', turn_id=turn_id), event(
        'item_completed', turn_id=turn_id, thread_id=SESSION,
        item={'type': 'Extension', 'kind': 'image_gen.generation', 'id': 'exec-1',
              'status': 'completed', 'result': ENCODED, 'failure': None,
              'savedPath': PREFIX + filename})]
    if displayed:
        rows.append({'type': 'response_item', 'payload': {
            'type': 'custom_tool_call_output', 'call_id': 'call-1',
            'output': [{'type': 'input_image', 'image_url': 'data:image/png;base64,' + ENCODED}],
            'internal_chat_message_metadata_passthrough': {'turn_id': turn_id}}})
    rows += [event('item_completed', turn_id=turn_id, thread_id=SESSION,
                   item={'type': 'AgentMessage', 'phase': 'final_answer',
                         'content': [{'type': 'Text', 'text': final}]}),
             event('task_complete', turn_id=turn_id, last_agent_message=final)]
    return rows


def write(home, rows, *, append=False):
    path = home / '.codex/sessions/2026/10/23' / f'rollout-date-{SESSION}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not append:
        rows = [{'type': 'session_meta', 'payload': {'id': SESSION}}] + rows
    with path.open('ab' if append else 'wb') as stream:
        for row in rows:
            stream.write(json.dumps(row).encode() + b'\n')
    return path


def test_first_turn_without_markdown_and_no_sensitive_output(tmp_path):
    assert native.snapshot(tmp_path, None) == {}
    write(tmp_path, turn())
    result = native.read_current(tmp_path, SESSION, {}, '完成')
    assert result == [{'path': PREFIX + 'exec-1.png',
                       'checksum': hashlib.sha256(PNG).hexdigest(), 'cli_turn_id': 'turn-1'}]
    assert ENCODED not in str(result)


@pytest.mark.parametrize('final,accepted', [
    ('![最终图](/work/final.png)', True),
    ('![图](' + PREFIX + 'exec-1.png)', True),
    ('![损坏引用](https://example.test/another.png)', True),
    ('## 草稿\n![预览](/work/draft.png)\n## 最终成品\n![图](' + PREFIX + 'exec-1.png)', True),
])
def test_history_authenticates_generation_without_prior_final_selection(tmp_path, final, accepted):
    write(tmp_path, turn(final=final))
    proof = native.read_history(tmp_path, SESSION, {PREFIX + 'exec-1.png'})
    assert bool(proof) is accepted


def test_resume_only_new_turn_and_history_targets(tmp_path):
    write(tmp_path, turn())
    cursor = native.snapshot(tmp_path, SESSION)
    write(tmp_path, turn('turn-2', 'exec-2.png'), append=True)
    assert native.read_current(tmp_path, SESSION, cursor, '完成')[0]['path'] == PREFIX + 'exec-2.png'
    assert native.read_history(tmp_path, SESSION, {PREFIX + 'exec-1.png'}) == {
        PREFIX + 'exec-1.png': hashlib.sha256(PNG).hexdigest()}


def test_unpresented_generation_and_unrelated_tool_are_not_deliveries(tmp_path):
    rows = turn(displayed=False)
    rows.insert(2, {'type': 'response_item', 'payload': {
        'type': 'reasoning', 'result': ENCODED}})
    rows.insert(2, event('item_completed', turn_id='turn-1', thread_id=SESSION,
                        item={'type': 'Extension', 'kind': 'another.tool', 'result': ENCODED}))
    write(tmp_path, rows)
    assert native.read_current(tmp_path, SESSION, {}, '完成') == []
    assert native.read_history(tmp_path, SESSION, {PREFIX + 'exec-1.png'}) == {
        PREFIX + 'exec-1.png': hashlib.sha256(PNG).hexdigest()}


def test_displayed_hash_must_match_generation(tmp_path):
    rows = turn()
    rows[2]['payload']['output'][0]['image_url'] += 'AAAA'
    write(tmp_path, rows)
    assert native.read_current(tmp_path, SESSION, {}, '完成') == []


@pytest.mark.parametrize('change', [
    lambda r: r[1]['payload']['item'].update(result='not base64'),
    lambda r: r[1]['payload']['item'].update(result=base64.b64encode(b'not png').decode()),
    lambda r: r[1]['payload'].update(thread_id='another-session'),
    lambda r: r[1]['payload'].update(turn_id='another-turn'),
    lambda r: r[1]['payload']['item'].update(savedPath=PREFIX + '../bad.png'),
    lambda r: r[1]['payload']['item'].update(savedPath=PREFIX.replace(SESSION, 'other') + 'bad.png'),
    lambda r: r[2]['payload']['internal_chat_message_metadata_passthrough'].update(turn_id='bad'),
    lambda r: r[2]['payload']['output'][0].update(image_url='data:image/png;base64,%%'),
    lambda r: r[-1]['payload'].update(turn_id='bad'),
    lambda r: r[-1]['payload'].update(last_agent_message='different'),
    lambda r: r[-1]['payload'].update(status='failed'),
    lambda r: r.pop(),
    lambda r: r.pop(-2),
    lambda r: r.insert(2, event('task_failed', turn_id='turn-1')),
])
def test_invalid_evidence_rejected(tmp_path, change):
    rows = turn()
    change(rows)
    write(tmp_path, rows)
    with pytest.raises(ValueError):
        native.read_current(tmp_path, SESSION, {}, '完成')


def test_bad_session_duplicate_fields_truncation_and_final(tmp_path):
    path = write(tmp_path, turn())
    with pytest.raises(ValueError):
        native.read_current(tmp_path, SESSION, {}, 'other final')
    path.write_bytes(path.read_bytes().replace(SESSION.encode(), b'wrong-session', 1))
    with pytest.raises(ValueError):
        native.snapshot(tmp_path, SESSION)
    path = write(tmp_path, turn())
    raw = path.read_bytes().splitlines(keepends=True)
    raw.insert(-1, b'{"type":"unknown","type":"unknown"}\n')
    path.write_bytes(b''.join(raw))
    with pytest.raises(ValueError):
        native.read_current(tmp_path, SESSION, {}, '完成')
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(ValueError):
        native.read_current(tmp_path, SESSION, {}, '完成')


def test_no_rollout_and_missing_resume(tmp_path):
    assert native.read_current(tmp_path, SESSION, {}, 'text') == []
    with pytest.raises(ValueError):
        native.snapshot(tmp_path, SESSION)
    with pytest.raises(ValueError):
        native.read_current(tmp_path, SESSION, {'offset': 1}, 'text')
    write(tmp_path, [])
    with pytest.raises(ValueError, match='no complete'):
        native.read_current(tmp_path, SESSION, {}, 'text')


def test_multiple_rollouts_or_turns_and_repeated_paths_rejected(tmp_path):
    path = write(tmp_path, turn() + turn('turn-2'))
    assert native.read_current(tmp_path, SESSION, {}, '完成')[0]['cli_turn_id'] == 'turn-1'
    with pytest.raises(ValueError):
        native.read_history(tmp_path, SESSION, {PREFIX + 'exec-1.png'})
    second = path.with_name(f'rollout-another-{SESSION}.jsonl')
    second.write_bytes(path.read_bytes())
    with pytest.raises(ValueError):
        native.snapshot(tmp_path, SESSION)


def test_hardlinks_rejected(tmp_path):
    path = write(tmp_path, turn())
    os.link(path, tmp_path / 'linked.jsonl')
    with pytest.raises(ValueError):
        native.snapshot(tmp_path, SESSION)


def test_symlinks_rejected(tmp_path):
    path = write(tmp_path, turn())
    source = tmp_path / 'source.jsonl'
    path.rename(source)
    try:
        path.symlink_to(source)
    except OSError:
        pytest.skip('OS denies symlink creation')
    with pytest.raises(ValueError):
        native.snapshot(tmp_path, SESSION)


def test_large_old_rollout_is_not_read_again(tmp_path, monkeypatch):
    path = write(tmp_path, turn())
    with path.open('ab') as stream:
        stream.write(json.dumps({'type': 'unknown', 'padding': 'x' * 100_000}).encode() + b'\n')
    cursor = native.snapshot(tmp_path, SESSION)
    write(tmp_path, turn('turn-2', 'exec-2.png'), append=True)
    monkeypatch.setattr(rollout, 'MAX_TOTAL', 5000)
    assert native.read_current(tmp_path, SESSION, cursor, '完成')[0]['cli_turn_id'] == 'turn-2'
    with pytest.raises(ValueError, match='512 MiB'):
        native.read_history(tmp_path, SESSION, {PREFIX + 'exec-1.png'})


def test_bounded_lines_identity_and_cursor(tmp_path, monkeypatch):
    path = write(tmp_path, turn())
    cursor = native.snapshot(tmp_path, SESSION)
    bad = dict(cursor, ino=-1)
    with pytest.raises(ValueError, match='identity'):
        native.read_current(tmp_path, SESSION, bad, '完成')
    bad = dict(cursor, offset=cursor['offset'] - 1)
    with pytest.raises(ValueError, match='boundary'):
        native.read_current(tmp_path, SESSION, bad, '完成')
    monkeypatch.setattr(rollout, 'MAX_LINE', 100)
    with pytest.raises(ValueError, match='64 MiB'):
        native.read_current(tmp_path, SESSION, {}, '完成')


def test_image_count_and_duplicate_paths(tmp_path, monkeypatch):
    rows = turn()
    rows.insert(2, rows[1])
    write(tmp_path, rows)
    with pytest.raises(ValueError, match='ambiguous'):
        native.read_current(tmp_path, SESSION, {}, '完成')
    write(tmp_path, turn())
    monkeypatch.setattr(native, 'MAX_IMAGES', 0)
    with pytest.raises(ValueError, match='Too many'):
        native.read_current(tmp_path, SESSION, {}, '完成')


@pytest.mark.parametrize('failure', ['event', 'generation', 'complete'])
def test_history_ignores_failed_turns_before_success(tmp_path, failure):
    rows = turn()
    if failure == 'event':
        rows.insert(1, event('task_failed', turn_id='turn-1'))
    elif failure == 'generation':
        rows[1]['payload']['item']['status'] = 'failed'
    else:
        rows[-1]['payload']['status'] = 'failed'
    write(tmp_path, rows + turn('turn-2', 'exec-2.png'))
    assert native.read_history(tmp_path, SESSION, {PREFIX + 'exec-1.png', PREFIX + 'exec-2.png'}) == {
        PREFIX + 'exec-2.png': hashlib.sha256(PNG).hexdigest()}
    if failure == 'generation':
        assert native.read_current(tmp_path, SESSION, {}, '完成') == []
    else:
        with pytest.raises(ValueError):
            native.read_current(tmp_path, SESSION, {}, '完成')


@pytest.mark.parametrize('final', ['这是草稿', '仅供预览，不是最终交付', 'Draft image'])
def test_history_does_not_require_formal_delivery_wording(tmp_path, final):
    write(tmp_path, turn(final=final))
    assert native.read_history(tmp_path, SESSION, {PREFIX + 'exec-1.png'}) == {
        PREFIX + 'exec-1.png': hashlib.sha256(PNG).hexdigest()}


@pytest.mark.parametrize('change', [dict(status='failed'), dict(failure={'message': 'failed'})])
def test_recovered_image_tool_failure_is_not_a_missing_deliverable(tmp_path, change):
    rows = turn()
    rows[1]['payload']['item'].update(change)
    write(tmp_path, rows)
    assert native.read_current(tmp_path, SESSION, {}, '完成') == []


@pytest.mark.parametrize('text_output_between', [False, True])
def test_viewed_image_is_not_delivery_even_when_pixels_match_generated_file(tmp_path, text_output_between):
    rows = turn()
    rows.insert(2, event('item_completed', turn_id='turn-1', thread_id=SESSION,
                        item={'type': 'ImageView', 'path': 'file:///work/reference.png'}))
    if text_output_between:
        rows.insert(3, {'type': 'response_item', 'payload': {
            'type': 'custom_tool_call_output', 'call_id': 'other', 'output': 'checked'}})
    write(tmp_path, rows)
    assert native.read_current(tmp_path, SESSION, {}, '完成') == []
