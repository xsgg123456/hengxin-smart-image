"""Isolated orchestration tests; substitutes never call a paid model."""
import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID
import pytest
from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.overseas.execution import claims, protocols, runner, reconcile
from app.overseas.execution.models import ExecutionGate, Job
from app.overseas.execution.queue import enqueue
from test_overseas_tasks import overseas, setup, create, payload


class Handler:
    def prepare(self, job, workspace):
        return 'Read frozen input.json and produce the protocol output.'

    def validate(self, job, workspace, summary):
        return {'validated': True, 'session': summary.session_id}


@pytest.fixture
def execution(overseas, tmp_path, monkeypatch):
    client, factory, _, designer = setup(overseas)
    task = UUID(create(client, payload(designer)).json()['id'])
    with factory.begin() as session:
        if session.get(ExecutionGate, 1) is None:
            session.add(ExecutionGate(id=1))
    settings = get_settings()
    settings.enable_codex_executor = True
    settings.codex_execution_root = str(tmp_path / 'execution')
    auth = tmp_path / 'auth.json'
    from test_managed_credentials import auth as credentials
    auth.write_text(json.dumps(credentials(ttl=86400)))
    settings.codex_auth_file = str(auth)
    settings.codex_binary = 'local-test-cli'
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **k:
                        SimpleNamespace(returncode=0, stdout=f'codex-cli {settings.codex_version}'))
    monkeypatch.setattr(runner, 'sandbox_command', lambda *a: ['local-test-cli'])
    monkeypatch.setattr(protocols, '_handlers', {'analysis': Handler()})
    def new(data=None):
        with factory.begin() as session:
            job = enqueue(session, task, 'analysis', str(__import__('uuid').uuid4()), data or {})
            return job.id
    return factory, new, settings


def fake_execute(mode=None):
    def execute(command, prompt, control, timeout, should_stop, started):
        started(123, 'test-boot', '456')
        if callable(mode):
            mode()
        if mode == 'unknown':
            raise OSError('private process diagnostics')
        events = [{'type': 'thread.started', 'thread_id': 'local-test-session'},
                  {'type': 'turn.completed'}]
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
        return {'exit_code': 0, 'reason': mode if isinstance(mode, str) else None}
    return execute


def test_success_duplicate_and_private_home(execution, monkeypatch):
    factory, new, settings = execution
    monkeypatch.setattr(runner, 'execute', fake_execute())
    first, second = new(), new()
    runner.run(factory, first)
    runner.run(factory, first)
    runner.run(factory, second)
    with factory() as session:
        row = session.get(Job, first)
        assert row.status == 'succeeded' and row.execution_count == 1 and row.process_exited
        assert row.result == {'validated': True, 'session': 'local-test-session'}
    from pathlib import Path
    homes = list(Path(settings.codex_execution_root).glob('*/home/.codex/auth.json'))
    assert len(homes) == 2 and homes[0].parent != homes[1].parent


def test_missing_protocol_fails_before_model(execution, monkeypatch):
    factory, new, _ = execution
    monkeypatch.setattr(protocols, '_handlers', {})
    monkeypatch.setattr(runner, 'execute', lambda *a: pytest.fail('Must never launch'))
    job_id = new()
    runner.run(factory, job_id)
    with factory() as session:
        row = session.get(Job, job_id)
        assert row.status == 'failed' and row.process_exited and row.process_id is None


@pytest.mark.parametrize('mode', ['timeout', 'output_limit'])
def test_stopped_failure_releases_only_after_return(execution, monkeypatch, mode):
    factory, new, _ = execution
    monkeypatch.setattr(runner, 'execute', fake_execute(mode))
    job_id = new()
    runner.run(factory, job_id)
    with factory() as session:
        row = session.get(Job, job_id)
        assert row.status == 'failed' and row.process_exited and row.result is None


def test_cancel_race_rejects_late_delivery(execution, monkeypatch):
    factory, new, _ = execution
    job_id = new()
    def cancel():
        with factory.begin() as session:
            row = claims.locked_job(session, job_id)
            row.cancel_requested, row.status = True, 'cancelling'
    monkeypatch.setattr(runner, 'execute', fake_execute(cancel))
    runner.run(factory, job_id)
    with factory() as session:
        row = session.get(Job, job_id)
        assert row.status == 'cancelled' and row.process_exited and row.result is None


def test_lost_lease_cannot_publish(execution, monkeypatch):
    factory, new, _ = execution
    job_id = new()
    def expire():
        with factory.begin() as session:
            session.get(Job, job_id).lease_until = utcnow() - timedelta(seconds=1)
    monkeypatch.setattr(runner, 'execute', fake_execute(expire))
    runner.run(factory, job_id)
    with factory() as session:
        assert session.get(Job, job_id).status == 'failed'
        assert session.get(Job, job_id).result is None


def test_unknown_process_retains_slot_until_confirmed(execution, monkeypatch):
    factory, new, _ = execution
    monkeypatch.setattr(runner, 'execute', fake_execute('unknown'))
    job_id = new()
    runner.run(factory, job_id)
    assert claims.claim(factory, job_id) is None
    monkeypatch.setattr(reconcile, 'same_process', lambda *args: True)
    assert reconcile.reconcile_once(factory) == 0
    with factory() as session:
        assert session.get(Job, job_id).status == 'uncertain'
        assert not session.get(Job, job_id).process_exited
    monkeypatch.setattr(reconcile, 'same_process', lambda *args: False)
    assert reconcile.reconcile_once(factory) == 1
    with factory() as session:
        assert session.get(Job, job_id).status == 'failed'
        assert session.get(Job, job_id).execution_count == 1


def test_no_identity_or_unavailable_inspection_stays_uncertain(execution, monkeypatch):
    factory, new, settings = execution
    job_id = new()
    token = claims.claim(factory, job_id)
    with factory.begin() as session:
        row = session.get(Job, job_id)
        row.worker_node, row.status = settings.worker_node_name, 'uncertain'
    assert reconcile.reconcile_once(factory) == 0
    with factory.begin() as session:
        row = session.get(Job, job_id)
        row.process_id, row.process_boot, row.process_started = 1, 'boot', '1'
    def unavailable(*args):
        raise OSError('No proc')
    monkeypatch.setattr(reconcile, 'same_process', unavailable)
    assert reconcile.reconcile_once(factory) == 0


def test_resource_pressure_does_not_claim(execution, monkeypatch):
    factory, new, _ = execution
    job_id = new()
    monkeypatch.setattr(runner, 'resources_available', lambda s: False)
    runner.run(factory, job_id)
    with factory() as session:
        assert session.get(Job, job_id).status == 'queued'
        assert session.get(Job, job_id).execution_count == 0


def test_skill_snapshot_is_frozen_and_traversal_rejected(execution, monkeypatch):
    factory, new, settings = execution
    source = {'skill': {'name': 'test-skill', 'files': {'SKILL.md': 'original'}}}
    job_id = new(source)
    source['skill']['files']['SKILL.md'] = 'changed'
    monkeypatch.setattr(runner, 'execute', fake_execute())
    runner.run(factory, job_id)
    from pathlib import Path
    path = next(Path(settings.codex_execution_root).glob('*/rounds/*/skills/test-skill/SKILL.md'))
    assert path.read_text() == 'original'
    bad = new({'skill': {'name': 'test-skill', 'files': {'SKILL.md': 'ok', '../escape': 'bad'}}})
    runner.run(factory, bad)
    with factory() as session:
        assert session.get(Job, bad).status == 'failed'


def test_protocol_publication_is_atomic_with_job_success(execution, monkeypatch):
    from app.overseas.tasks.models import Task
    factory, new, _ = execution
    class Publishing(Handler):
        def publish(self, session, job, result):
            session.get(Task, job.task_id).remarks = 'published'
    protocols._handlers['analysis'] = Publishing()
    monkeypatch.setattr(runner, 'execute', fake_execute())
    job_id = new()
    runner.run(factory, job_id)
    with factory() as session:
        job = session.get(Job, job_id)
        assert job.status == 'succeeded'
        assert session.get(Task, job.task_id).remarks == 'published'


def test_publication_exception_rolls_back_business_change(execution, monkeypatch):
    from app.overseas.tasks.models import Task
    factory, new, _ = execution
    class Failing(Handler):
        def publish(self, session, job, result):
            session.get(Task, job.task_id).remarks = 'must roll back'
            raise ValueError('private backend detail')
    protocols._handlers['analysis'] = Failing()
    monkeypatch.setattr(runner, 'execute', fake_execute())
    job_id = new()
    runner.run(factory, job_id)
    with factory() as session:
        job = session.get(Job, job_id)
        assert job.status == 'failed' and job.result is None
        assert session.get(Task, job.task_id).remarks == '说明'


def test_exit_zero_without_completed_stream_cannot_succeed(execution, monkeypatch):
    factory, new, _ = execution
    def incomplete(command, prompt, control, timeout, should_stop, started):
        started(123, 'boot', '1')
        (control / 'events.jsonl').write_text('{"type":"thread.started","thread_id":"local"}')
        return {'exit_code': 0, 'reason': None}
    monkeypatch.setattr(runner, 'execute', incomplete)
    job_id = new()
    runner.run(factory, job_id)
    with factory() as session:
        assert session.get(Job, job_id).status == 'failed'


@pytest.mark.parametrize('failure', [False, True])
def test_usage_is_not_persisted_and_frozen_timeout_is_local(execution, monkeypatch, failure):
    factory, new, settings = execution
    original = settings.codex_timeout_seconds
    timeouts = []
    def execute(command, prompt, control, timeout, should_stop, started):
        timeouts.append(timeout)
        started(123, 'boot', '1')
        events = [{'type': 'thread.started', 'thread_id': 'local'}, {'type': 'turn.completed',
                  'usage': {'input_tokens': 10, 'output_tokens': 20}}]
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
        return {'exit_code': 1 if failure else 0}
    monkeypatch.setattr(runner, 'execute', execute)
    identity = new({'runtime': {'timeoutSeconds': 120}})
    runner.run(factory, identity)
    legacy = new()
    runner.run(factory, legacy)
    assert timeouts == [120, original] and settings.codex_timeout_seconds == original
    with factory() as session:
        job = session.get(Job, identity)
        assert not hasattr(job, 'usage')
        assert job.status == ('failed' if failure else 'succeeded')
