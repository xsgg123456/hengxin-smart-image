"""Native-only historical recovery binds one business turn to one native turn."""
import json
from hashlib import sha256
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from app.overseas.studio.models import Turn, Conversation, Picture
from app.overseas.execution.models import Job
from app.overseas.tasks.models import ExecutionObject
from test_studio_image_recovery import missed, run, count, studio, materials, overseas


@pytest.fixture
def native_only(missed):
    reply = '已依据实拍款式生成拼版图。'
    with missed.factory.begin() as s:
        target = s.get(Turn, UUID(missed.turn['id']))
        prior = s.scalar(select(Turn).where(Turn.id != target.id))
        other = Conversation(id=uuid4(), task_id=target.task_id, session_id='other-session')
        s.add(other)
        prior.conversation_id = other.id
        old_job = s.get(Job, prior.job_id)
        old_job.payload = {**old_job.payload, 'conversationId': str(other.id)}
        target.reply = reply
        job = s.get(Job, target.job_id)
        job.result = {**job.result, 'reply': reply}
        rows = [json.loads(line) for line in missed.events.read_text().splitlines()]
        rows[-2]['item']['text'] = reply
        raw = '\n'.join(json.dumps(row) for row in rows).encode()
        missed.events.write_bytes(raw)
        target.event_offset = len(raw)
        missed.digest = sha256(raw).hexdigest()
    history = [json.loads(line) for line in missed.history.read_text().splitlines()]
    history = json.loads(json.dumps(history, ensure_ascii=False).replace('已交付', reply))
    missed.history.write_text(''.join(json.dumps(row) + '\n' for row in history))
    return missed


def test_native_only_recovery_preserves_reply_and_is_idempotent(native_only):
    case = native_only
    assert run(case)['status'] == 'eligible'
    assert count(case, Picture) == count(case, ExecutionObject) == 0
    assert run(case, apply=True)['status'] == 'succeeded'
    assert run(case, apply=True)['status'] == 'already_recovered'
    assert count(case, Picture) == count(case, ExecutionObject) == 1
    with case.factory() as s:
        turn = s.get(Turn, UUID(case.turn['id']))
        assert turn.reply == '已依据实拍款式生成拼版图。'
        assert s.get(Job, turn.job_id).execution_count == 1


@pytest.mark.parametrize('damage', ['business_turns', 'native_turns', 'unpresented',
    'truncated', 'different_final', 'changed_image', 'failed', 'cross_session'])
def test_native_only_uncertainty_never_writes(native_only, damage):
    case = native_only
    rows = [json.loads(line) for line in case.history.read_text().splitlines()]
    if damage == 'business_turns':
        with case.factory.begin() as s:
            target = s.get(Turn, UUID(case.turn['id']))
            prior = s.scalar(select(Turn).where(Turn.id != target.id))
            prior.conversation_id = target.conversation_id
    elif damage == 'native_turns':
        extra = json.loads(json.dumps(rows[1:]).replace('turn-1', 'turn-2'))
        rows.extend(extra)
    elif damage == 'different_final':
        rows = json.loads(json.dumps(rows, ensure_ascii=False).replace('已依据实拍款式生成拼版图。',
            '另一轮的最终回复'))
    elif damage == 'unpresented':
        rows = [row for row in rows if row.get('payload', {}).get('type') != 'custom_tool_call_output']
    elif damage == 'truncated': rows.pop()
    elif damage == 'changed_image': case.image.write_bytes(b'corrupted')
    elif damage == 'failed': rows[-1]['payload']['status'] = 'failed'
    elif damage == 'cross_session': rows[0]['payload']['id'] = 'other-session'
    case.history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    with pytest.raises(ValueError):
        run(case, apply=True)
    assert count(case, Picture) == count(case, ExecutionObject) == 0


def test_native_final_presentation_is_recovered_regardless_of_preview_wording(native_only):
    case = native_only
    reply = '仅供预览，待确认。'
    rows = [json.loads(line) for line in case.history.read_text().splitlines()]
    rows = json.loads(json.dumps(rows, ensure_ascii=False).replace(
        '已依据实拍款式生成拼版图。', reply))
    case.history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    with case.factory.begin() as session:
        target = session.get(Turn, UUID(case.turn['id']))
        target.reply = reply
        job = session.get(Job, target.job_id)
        job.result = {**job.result, 'reply': reply}
        events = [json.loads(line) for line in case.events.read_text().splitlines()]
        events[-2]['item']['text'] = reply
        raw = '\n'.join(json.dumps(row) for row in events).encode()
        case.events.write_bytes(raw)
        case.digest, target.event_offset = sha256(raw).hexdigest(), len(raw)
    assert run(case)['status'] == 'eligible'
    assert run(case, apply=True)['status'] == 'succeeded'
    assert run(case, apply=True)['status'] == 'already_recovered'
    assert count(case, Picture) == count(case, ExecutionObject) == 1
    with case.factory() as session:
        target = session.get(Turn, UUID(case.turn['id']))
        assert target.reply == reply
        assert session.get(Job, target.job_id).execution_count == 1
