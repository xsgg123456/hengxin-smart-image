"""Repair only a verified legacy text failure, with atomic audit and no rerun."""
from hashlib import sha256
from uuid import UUID
import pytest
from sqlalchemy import select, func
from app.overseas.execution import runner
from app.overseas.execution.events import MESSAGES
from app.overseas.execution.models import Job
from app.overseas.management.models import Audit
from app.overseas.studio.models import Turn
from app.overseas.studio.recovery import recover
from test_overseas_studio import studio, send
from test_overseas_studio_execution import fake_runtime
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT
from test_cli_event_json import wire


def legacy_failure(studio, monkeypatch, tmp_path):
    client, factory, actor, task, _, _ = studio
    commands = fake_runtime(studio, monkeypatch, tmp_path)
    def execute(command, prompt, control, timeout, monitor, started):
        started(123, 'boot', 'birth')
        (control / 'events.jsonl').write_text(wire(), encoding='utf-8')
        (control / 'exit.json').write_text('{"exit_code":0,"reason":null}')
        return dict(exit_code=0)
    monkeypatch.setattr(runner, 'execute', execute)
    turn = send(client, task).json()['turns'][0]
    runner.run(factory, turn['jobId'])
    with factory.begin() as session:
        job = session.get(Job, UUID(turn['jobId']))
        assert job.status == 'succeeded'
        job.status, job.result, job.error = 'failed', None, MESSAGES['failed']
    path = commands[0][0].control / 'events.jsonl'
    return turn, path, sha256(path.read_bytes()).hexdigest()


def test_dry_run_apply_idempotency_and_audit(studio, monkeypatch, tmp_path):
    client, factory, actor, task, _, _ = studio
    turn, path, digest = legacy_failure(studio, monkeypatch, tmp_path)
    def no_execution(*_):
        raise AssertionError('Recovery must not invoke model')
    monkeypatch.setattr(runner, 'execute', no_execution)
    with factory() as session:
        completed = session.get(Job, UUID(turn['jobId'])).completed_at
    assert recover(factory, turn['id'], actor, digest)['status'] == 'eligible'
    with factory() as session:
        assert session.get(Job, UUID(turn['jobId'])).status == 'failed'
        assert session.scalar(select(func.count()).select_from(Audit).where(
            Audit.action == 'studio.text_recovery')) == 0
    assert recover(factory, turn['id'], actor, digest, apply=True)['status'] == 'succeeded'
    assert recover(factory, turn['id'], actor, digest, apply=True)['status'] == 'already_recovered'
    with factory() as session:
        job = session.get(Job, UUID(turn['jobId']))
        assert job.execution_count == 1 and job.completed_at == completed and job.error is None
        assert session.scalar(select(func.count()).select_from(Audit).where(
            Audit.action == 'studio.text_recovery')) == 1
    row = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()['turns'][0]
    assert row['status'] == 'succeeded' and row['reply'] == '完整最终回复'


@pytest.mark.parametrize('mode', ['hash', 'receipt', 'text', 'session', 'later', 'cancel', 'running', 'image'])
def test_repair_refuses_unsafe_or_changed_evidence(studio, monkeypatch, tmp_path, mode):
    client, factory, actor, task, _, _ = studio
    turn, path, digest = legacy_failure(studio, monkeypatch, tmp_path)
    if mode == 'hash':
        digest = '0' * 64
    elif mode == 'receipt':
        (path.parent / 'exit.json').write_text('{"exit_code":1}')
    elif mode == 'later':
        assert send(client, task, key='later').status_code == 200
    else:
        with factory.begin() as session:
            job = session.get(Job, UUID(turn['jobId']))
            row = session.get(Turn, UUID(turn['id']))
            if mode == 'text':
                row.reply = 'changed'
            elif mode == 'session':
                row.event_session_id = 'different'
            elif mode == 'cancel':
                job.cancel_requested = True
            elif mode == 'running':
                job.process_exited = False
            elif mode == 'image':
                text = '![final](/work/final.png)'
                raw = path.read_text(encoding='utf-8').replace('完整最终回复', text)
                path.write_text(raw, encoding='utf-8')
                digest = sha256(path.read_bytes()).hexdigest()
                row.reply, row.event_offset = text, len(path.read_bytes())
    with pytest.raises(ValueError):
        recover(factory, turn['id'], actor, digest, apply=True)
    with factory() as session:
        assert session.get(Job, UUID(turn['jobId'])).status == 'failed'


def test_publish_failure_rolls_back(studio, monkeypatch, tmp_path):
    _, factory, actor, _, _, _ = studio
    turn, _, digest = legacy_failure(studio, monkeypatch, tmp_path)
    from app.overseas.studio.recovery import HANDLER
    monkeypatch.setattr(HANDLER, 'publish', lambda *_: (_ for _ in ()).throw(ValueError('publish failed')))
    with pytest.raises(ValueError, match='publish failed'):
        recover(factory, turn['id'], actor, digest, apply=True)
    with factory() as session:
        assert session.get(Job, UUID(turn['jobId'])).status == 'failed'
