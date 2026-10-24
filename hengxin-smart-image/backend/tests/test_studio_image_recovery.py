"""Operator recovery uses real DB, native evidence, image validation and storage."""
import base64
import json
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import select, func
from app.core.config import get_settings
from app.overseas.execution.models import Job, JobOutbox, ExecutionGate
from app.overseas.management.models import Audit
from app.overseas.studio import image_recovery as recovery
from app.overseas.studio.models import Turn, Picture, Conversation
from app.overseas.tasks.models import Task, TaskDeletion, ExecutionObject
from test_overseas_studio import studio, send, finish
from test_overseas_materials import materials
from test_overseas_tasks import overseas
from test_overseas_assignment import change_roles
from test_studio_native_images import turn as native_turn, SESSION, ENCODED


@pytest.fixture
def missed(studio, tmp_path):
    client, factory, actor, task, _, store = studio
    first = send(client, task).json()['turns'][0]
    finish(factory, first)
    second = send(client, task, key='second').json()['turns'][-1]
    finish(factory, second)
    target = '/home/runner/.codex/generated_images/thread-1/exec-1.png'
    reply = f'![正式成品]({target})\n[下载]({target})'
    output = BytesIO()
    Image.new('RGB', (24, 32), 'blue').save(output, format='PNG')
    data = output.getvalue()
    get_settings().codex_execution_root = str(tmp_path / 'execution')
    with factory.begin() as session:
        row = session.get(Turn, UUID(second['id']))
        base = tmp_path / 'execution' / 'studio' / str(row.conversation_id)
        row.dispatched, row.reply, row.event_session_id = True, reply, 'thread-1'
        row.delivery_error = '图片收取失败'
        job = session.get(Job, row.job_id)
        job.result = dict(reply=reply, sessionId='thread-1', pictures=[], deliveryError=row.delivery_error)
        session.get(ExecutionGate, 1).paused = True
        control = base / 'control' / second['id']
        control.mkdir(parents=True)
        events = [dict(type='thread.started', thread_id='thread-1'), dict(type='turn.started'),
                  dict(type='item.completed', item=dict(type='agent_message', text=reply)),
                  dict(type='turn.completed')]
        raw = '\n'.join(json.dumps(e) for e in events).encode()
        (control / 'events.jsonl').write_bytes(raw)
        (control / 'exit.json').write_text('{"exit_code":0,"reason":null}')
        row.event_offset = len(raw)
    image = base / 'home/.codex/generated_images/thread-1/exec-1.png'
    image.parent.mkdir(parents=True)
    image.write_bytes(data)
    history = base / 'home/.codex/sessions/rollout-thread-1.jsonl'
    history.parent.mkdir(parents=True)
    rows = [{'type': 'session_meta', 'payload': {'id': 'thread-1'}}]
    original = native_turn(final='已交付')
    original = json.loads(json.dumps(original).replace(SESSION, 'thread-1').replace(
        ENCODED, base64.b64encode(data).decode()))
    rows += original
    history.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    return SimpleNamespace(factory=factory, actor=actor, task=task, turn=second, store=store,
        events=control / 'events.jsonl', history=history, image=image, target=target,
        digest=sha256(raw).hexdigest(), data=data, client=client)


def run(case, **kwargs):
    return recovery.recover(case.factory, case.turn['id'], case.actor, case.digest,
                            store=case.store, **kwargs)


def count(case, model):
    with case.factory() as session:
        return session.scalar(select(func.count()).select_from(model))


def test_dry_run_repair_replay_and_accounting(missed):
    before_objects = dict(missed.store.data)
    with missed.factory() as session:
        job = session.get(Job, UUID(missed.turn['jobId']))
        original = job.completed_at, job.execution_count, job.started_at
    report = run(missed)
    assert report['status'] == 'eligible' and report['paths'] == [missed.target]
    assert report['pictureCount'] == 1 and report['checksums'] == [sha256(missed.data).hexdigest()]
    assert count(missed, Picture) == count(missed, ExecutionObject) == 0
    assert missed.store.data == before_objects
    assert run(missed, apply=True)['status'] == 'succeeded'
    assert run(missed, apply=True)['status'] == 'already_recovered'
    assert count(missed, Picture) == count(missed, ExecutionObject) == 1
    assert len(missed.store.data) == len(before_objects) + 1
    with missed.factory() as session:
        job = session.get(Job, UUID(missed.turn['jobId']))
        turn = session.get(Turn, UUID(missed.turn['id']))
        picture = session.scalar(select(Picture))
        assert (job.completed_at, job.execution_count, job.started_at) == original
        assert job.result['pictures'][0]['id'] == str(picture.id)
        assert job.result['deliveryError'] is None and turn.delivery_error is None
        assert picture.turn_id == turn.id and picture.source_path == missed.target
        audits = session.scalars(select(Audit).where(Audit.action == 'studio.image_recovery')).all()
        assert len(audits) == 1 and 'reply' not in audits[0].after
        assert session.get(Task, UUID(missed.task['id'])).status == 'studio'


@pytest.mark.parametrize('mode', ['hash', 'receipt', 'reason', 'text', 'session', 'payload',
    'job_owner', 'channel_owner', 'failed', 'cancelled', 'cancel', 'running', 'queued',
    'deleted', 'archived', 'unpaused', 'outbox', 'event_invalid', 'event_incomplete',
    'history_incomplete', 'image_hash', 'invalid_reference', 'permissions'])
def test_unsafe_recovery_never_writes(missed, mode):
    if mode == 'hash':
        missed.digest = '0' * 64
    elif mode in ('receipt', 'reason'):
        missed.events.with_name('exit.json').write_text(json.dumps(
            dict(exit_code=1 if mode == 'receipt' else 0, reason='aborted' if mode == 'reason' else None)))
    elif mode == 'history_incomplete':
        lines = missed.history.read_text().splitlines()
        missed.history.write_text('\n'.join(lines[:-1]) + '\n')
    elif mode == 'image_hash':
        Image.new('RGB', (24, 32), 'red').save(missed.image)
    elif mode == 'permissions':
        change_roles(missed.factory, missed.actor, ('designer',))
    else:
        with missed.factory.begin() as session:
            turn = session.get(Turn, UUID(missed.turn['id']))
            job = session.get(Job, turn.job_id)
            if mode == 'text': turn.reply = 'different'
            elif mode == 'session': turn.event_session_id = 'different'
            elif mode == 'payload': job.payload = {**job.payload, 'turnId': str(uuid4())}
            elif mode == 'job_owner': job.task_id = uuid4()
            elif mode == 'channel_owner': session.get(Conversation, turn.conversation_id).task_id = uuid4()
            elif mode in ('failed', 'cancelled', 'running'): job.status = mode
            elif mode == 'cancel': job.cancel_requested = True
            elif mode == 'queued':
                session.add(Job(task_id=turn.task_id, kind='studio', payload={}, dedupe_key='later'))
            elif mode == 'deleted':
                session.add(TaskDeletion(task_id=turn.task_id, actor_id=missed.actor))
            elif mode == 'archived': session.get(Task, turn.task_id).status = 'archived'
            elif mode == 'unpaused': session.get(ExecutionGate, 1).paused = False
            elif mode == 'outbox': session.get(JobOutbox, job.id).completed_at = None
            elif mode == 'event_invalid': turn.event_invalid = True
            elif mode in ('event_incomplete', 'invalid_reference'):
                events = [json.loads(line) for line in missed.events.read_text().splitlines()]
                if mode == 'event_incomplete': events.pop()
                else:
                    turn.reply += '\n![bad](/work/../private.png)'
                    events[-2]['item']['text'] = turn.reply
                    job.result = {**job.result, 'reply': turn.reply}
                raw = '\n'.join(json.dumps(e) for e in events).encode()
                missed.events.write_bytes(raw)
                missed.digest, turn.event_offset = sha256(raw).hexdigest(), len(raw)
    with pytest.raises((ValueError, HTTPException)):
        run(missed, apply=True)
    assert count(missed, Picture) == count(missed, ExecutionObject) == 0


def test_explicit_final_reference_recovers_same_session_image_not_previously_presented(missed):
    lines = missed.history.read_text().splitlines()
    missed.history.write_text('\n'.join(
        line for line in lines if 'custom_tool_call_output' not in line) + '\n')
    assert run(missed)['status'] == 'eligible'
    assert count(missed, Picture) == count(missed, ExecutionObject) == 0
    assert run(missed, apply=True)['status'] == 'succeeded'
    assert run(missed, apply=True)['status'] == 'already_recovered'
    assert count(missed, Picture) == count(missed, ExecutionObject) == 1
    with missed.factory() as session:
        picture = session.scalar(select(Picture))
        assert picture.source_path == missed.target
        assert picture.checksum == sha256(missed.data).hexdigest()


def test_failed_storage_has_durable_ledger_and_retry_is_idempotent(missed, monkeypatch):
    original = missed.store.put
    def fail(record, data):
        assert count(missed, ExecutionObject) == 1
        raise RuntimeError('storage unavailable')
    monkeypatch.setattr(missed.store, 'put', fail)
    with pytest.raises(RuntimeError, match='storage unavailable'):
        run(missed, apply=True)
    assert count(missed, ExecutionObject) == 1 and count(missed, Picture) == 0
    monkeypatch.setattr(missed.store, 'put', original)
    assert run(missed, apply=True)['status'] == 'succeeded'
    assert count(missed, ExecutionObject) == count(missed, Picture) == 1


def test_database_failure_after_upload_reuses_same_object(missed, monkeypatch):
    original = recovery.record
    monkeypatch.setattr(recovery, 'record', lambda *_: (_ for _ in ()).throw(ValueError('db failed')))
    with pytest.raises(ValueError, match='db failed'):
        run(missed, apply=True)
    objects = dict(missed.store.data)
    assert count(missed, Picture) == 0 and count(missed, ExecutionObject) == 1
    monkeypatch.setattr(recovery, 'record', original)
    assert run(missed, apply=True)['status'] == 'succeeded'
    assert missed.store.data == objects


@pytest.mark.parametrize('mode', ['delete', 'queued', 'unpause'])
def test_state_change_between_ledger_and_upload_blocks_write(missed, monkeypatch, mode):
    original, calls = recovery._locked, []
    def changed(session, turn_id, actor_id):
        calls.append(True)
        if len(calls) == 2:
            with missed.factory.begin() as other:
                if mode == 'delete':
                    other.add(TaskDeletion(task_id=UUID(missed.task['id']), actor_id=actor_id))
                elif mode == 'queued':
                    other.add(Job(task_id=UUID(missed.task['id']), kind='studio', payload={}, dedupe_key='race'))
                else: other.get(ExecutionGate, 1).paused = False
        return original(session, turn_id, actor_id)
    monkeypatch.setattr(recovery, '_locked', changed)
    objects = dict(missed.store.data)
    with pytest.raises(ValueError):
        run(missed, apply=True)
    assert missed.store.data == objects and count(missed, Picture) == 0
    assert count(missed, ExecutionObject) == 1


def test_existing_picture_in_prior_turn_of_same_conversation_is_not_duplicated(missed):
    assert run(missed, apply=True)['status'] == 'succeeded'
    with missed.factory.begin() as session:
        prior = session.scalar(select(Turn).where(Turn.id != UUID(missed.turn['id'])))
        session.scalar(select(Picture)).turn_id = prior.id
    objects = dict(missed.store.data)
    assert run(missed, apply=True)['status'] == 'already_recovered'
    assert count(missed, Picture) == count(missed, ExecutionObject) == 1
    assert missed.store.data == objects


@pytest.mark.parametrize('mode', ['events', 'image', 'ledger'])
def test_evidence_or_ledger_change_between_transactions_prevents_storage(missed, monkeypatch, mode):
    original, calls = recovery._locked, []
    def changed(session, turn_id, actor_id):
        calls.append(True)
        if len(calls) == 2:
            if mode == 'events':
                missed.events.write_bytes(missed.events.read_bytes() + b'\n')
            elif mode == 'image':
                Image.new('RGB', (24, 32), 'red').save(missed.image)
            else:
                with missed.factory.begin() as other:
                    other.delete(other.scalar(select(ExecutionObject)))
        return original(session, turn_id, actor_id)
    monkeypatch.setattr(recovery, '_locked', changed)
    objects = dict(missed.store.data)
    with pytest.raises(ValueError):
        run(missed, apply=True)
    assert missed.store.data == objects and count(missed, Picture) == 0


def test_hardlinked_image_is_not_recovered(missed, tmp_path):
    import os
    os.link(missed.image, tmp_path / 'alias.png')
    with pytest.raises(ValueError):
        run(missed, apply=True)
    assert count(missed, Picture) == count(missed, ExecutionObject) == 0


def test_matching_native_proof_still_requires_valid_image(missed):
    bad = b'\x89PNG\r\n\x1a\ncorrupt-image'
    missed.history.write_text(missed.history.read_text().replace(
        base64.b64encode(missed.data).decode(), base64.b64encode(bad).decode()))
    missed.image.write_bytes(bad)
    with pytest.raises(HTTPException):
        run(missed, apply=True)
    assert count(missed, Picture) == count(missed, ExecutionObject) == 0
