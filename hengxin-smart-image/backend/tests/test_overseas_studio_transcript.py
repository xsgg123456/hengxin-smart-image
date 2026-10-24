"""Real HTTP and worker persistence, no paid execution."""
import json
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from app.overseas.execution import runner, claims
from app.overseas.execution.models import Job
from app.overseas.studio import delivery, transcript
from app.overseas.studio.models import Turn, Transcript
from test_overseas_studio import studio, send
from test_overseas_studio_execution import fake_runtime
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT
from test_overseas_assignment import change_roles
from studio_delivery_helpers import DeliveryCase
from studio_receipt_regression_helpers import take


def read(client, task, after=0):
    return client.get(f"{ROOT}/tasks/{task['id']}/studio/transcript?after={after}")


def event(kind, text, identity='message', stage='completed'):
    return dict(type='item.' + stage, item=dict(id=identity, type=kind, text=text))


def encode(events):
    return ('\n'.join(json.dumps(e, ensure_ascii=False) for e in events)).encode()


def claimed(studio, tmp_path):
    client, factory, _, task, _, _ = studio
    turn = send(client, task).json()['turns'][0]
    identity = UUID(turn['jobId'])
    token = claims.claim(factory, identity)
    with factory() as session:
        job = session.get(Job, identity)
        session.expunge(job)
    workspace = SimpleNamespace(control=tmp_path)
    return job, token, workspace


def test_full_ordered_updates_partial_utf8_reconnect_and_safe_tools(studio, tmp_path):
    client, factory, actor, task, _, _ = studio
    job, token, workspace = claimed(studio, tmp_path)
    path = tmp_path / 'events.jsonl'
    long_text = '完整文字🙂' * 3000 + '\n```python\nprint(1)\n```'
    events = [dict(type='thread.started', thread_id='thread-1'),
              event('agent_message', '开始', stage='started'),
              event('agent_message', long_text, stage='updated'),
              event('agent_message', long_text),
              event('reasoning', '公开的推理摘要', 'summary'),
              dict(type='item.completed', item=dict(id='tool', type='command_execution',
                   command='SECRET_API_KEY', aggregated_output='PRIVATE_STDOUT')),
              event('hidden_reasoning', 'PRIVATE_CHAIN', 'hidden'),
              event('agent_message', '最后公开文字', 'last')]
    raw = encode(events)
    boundary = raw.index('最后'.encode()) + 1
    path.write_bytes(raw[:boundary])
    transcript.poll(factory, job, token, workspace)
    first = read(client, task).json()
    assert len(first['items']) == 5
    assert [r['state'] for r in first['items'][:3]] == ['running', 'running', 'completed']
    assert first['items'][2]['text'] == long_text
    assert 'SECRET' not in json.dumps(first) and 'PRIVATE' not in json.dumps(first)
    transcript.poll(factory, job, token, workspace)
    assert read(client, task, first['cursor']).json()['items'] == []
    with path.open('ab') as output:
        output.write(raw[boundary:])
    transcript.poll(factory, job, token, workspace)
    assert read(client, task, first['cursor']).json()['items'] == []
    transcript.poll(factory, job, token, workspace, final=True)
    last = read(client, task, first['cursor']).json()
    assert len(last['items']) == 1 and last['items'][0]['text'] == '最后公开文字'
    transcript.poll(factory, job, token, workspace, final=True)
    assert read(client, task, last['cursor']).json()['items'] == []
    change_roles(factory, actor, ('designer',))
    assert read(client, task).status_code == 403


def test_claim_and_session_fences_reject_unowned_text(studio, tmp_path):
    client, factory, _, task, _, _ = studio
    job, token, workspace = claimed(studio, tmp_path)
    path = tmp_path / 'events.jsonl'
    path.write_bytes(encode([event('agent_message', 'before session'),
        dict(type='thread.started', thread_id='correct'), event('agent_message', 'owned'),
        dict(type='thread.started', thread_id='wrong'), event('agent_message', 'unowned')]) + b'\n')
    transcript.poll(factory, job, uuid4(), workspace)
    assert read(client, task).json()['items'] == []
    transcript.poll(factory, job, token, workspace)
    assert [r['text'] for r in read(client, task).json()['items']] == ['owned']


@pytest.mark.parametrize('mode', ['failure', 'cancel', 'crash'])
def test_failed_and_cancelled_runner_keep_final_public_text(studio, monkeypatch, tmp_path, mode):
    client, factory, _, task, _, _ = studio
    fake_runtime(studio, monkeypatch, tmp_path)
    turn = send(client, task).json()['turns'][0]
    def execute(command, prompt, control, timeout, monitor, started):
        started(123, 'boot', 'birth')
        (control / 'events.jsonl').write_bytes(encode([
            dict(type='thread.started', thread_id='session-123'),
            event('agent_message', '失败也保留的完整文字')]))
        if mode == 'cancel':
            with factory.begin() as session:
                job = session.get(Job, UUID(turn['jobId']))
                job.cancel_requested, job.status = True, 'cancelling'
        if mode == 'crash':
            raise RuntimeError('unconfirmed process exit')
        return dict(exit_code=1)
    monkeypatch.setattr(runner, 'execute', execute)
    runner.run(factory, turn['jobId'])
    result = read(client, task).json()
    assert [i['text'] for i in result['items']] == ['失败也保留的完整文字']
    with factory() as session:
        assert session.get(Turn, UUID(turn['id'])).reply == '失败也保留的完整文字'
        assert session.get(Job, UUID(turn['jobId'])).status == {
            'failure': 'failed', 'cancel': 'cancelled', 'crash': 'uncertain'}[mode]


@pytest.mark.parametrize('boundary', ['enumerate_delivery', 'collect_reference', 'put'])
def test_collection_failure_keeps_raw_reply_and_transcript(studio, monkeypatch, tmp_path, boundary):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    calls = []

    def broken(*_args, **_kwargs):
        calls.append(True)
        raise OSError('collection temporarily unavailable')

    owner = case.store if boundary == 'put' else delivery
    with monkeypatch.context() as patch:
        patch.setattr(owner, boundary, broken)
        case.run()
    row = case.current()
    assert calls and row['status'] == 'succeeded' and row['pictures'] == []
    assert row['deliveryStatus'] == dict(
        state='partial',
        expected=None if boundary == 'enumerate_delivery' else 1, saved=0)
    assert row['reply'] == '![设计](/work/output0.png)\n'
    assert read(case.client, case.task).json()['items'][0]['text'] == row['reply']
    assert case.job().completed_at is not None and case.view()['activeTurnId'] is None
    case.recover()
    assert case.current()['pictures'] == []
    take(case, source='snapshot' if boundary == 'put' else 'work')
    assert len(case.current()['pictures']) == 1
    assert case.current()['reply'] == row['reply']
    assert read(case.client, case.task).json()['items'][0]['text'] == row['reply']
    assert case.downloaded() == [(case.workspace.work / 'output0.png').read_bytes()]
    assert send(case.client, case.task, key='continue').status_code == 200


def test_transcript_pagination_does_not_skip_rows(studio, tmp_path):
    client, factory, _, task, _, _ = studio
    job, _, _ = claimed(studio, tmp_path)
    with factory.begin() as session:
        turn = session.get(Turn, UUID(job.payload['turnId']))
        session.add_all([Transcript(task_id=turn.task_id, turn_id=turn.id,
            item_id=str(i), kind='message', text=str(i), state='completed') for i in range(502)])
    first = read(client, task).json()
    second = read(client, task, first['cursor']).json()
    assert len(first['items']) == 500 and first['hasMore']
    assert len(second['items']) == 2 and not second['hasMore']
    assert [r['text'] for r in second['items']] == ['500', '501']
