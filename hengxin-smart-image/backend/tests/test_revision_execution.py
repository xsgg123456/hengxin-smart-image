import base64
import json
from uuid import UUID

from sqlalchemy import select

from app.execution import codex_runner as runner
from app.execution.provenance import verify_provenance
from app.modules.tasks.models import ResultSlotRecord, RoundRecord
from app.modules.tasks.attempts import ExecutionSession
from app.models import Job
from app.worker import reconcile
from files_helpers import files_env, image_bytes  # noqa: F401
from test_tasks import task_env, job_for  # noqa: F401
from test_execution_reconcile import recovery, state  # noqa: F401
from test_codex_runner import real_env, frozen_request, cli  # noqa: F401


def test_partial_recovery_uses_real_provenance_parser_and_no_new_execution(recovery, monkeypatch):
    factory, store, _, _, task_id, round_id, control, _ = recovery
    with factory.begin() as session:
        session.add(ResultSlotRecord(task_id=task_id, slot=1))
    home = control.parents[1] / 'home/.codex'
    (home / 'generated_images/session-a/fresh.png').rename(home / 'generated_images/session-a/exec-fresh.png')
    logs = home / 'sessions/2026/09/10'
    logs.mkdir(parents=True)
    records = [{'type': 'task_started', 'turn_id': 't1'},
        {'type': 'item_completed', 'thread_id': 'session-a', 'turn_id': 't1', 'item': {
            'type': 'Extension', 'kind': 'image_gen.generation', 'id': 'exec-fresh',
            'status': 'completed', 'failure': None,
            'savedPath': '/home/runner/.codex/generated_images/session-a/exec-fresh.png',
            'result': base64.b64encode(image_bytes()).decode()}}]
    (logs / 'rollout-test-session-a.jsonl').write_text(''.join(
        json.dumps({'type': 'event_msg', 'payload': item}) + '\n' for item in records))
    work = control.parents[1] / 'rounds' / str(round_id)
    work.mkdir(parents=True)
    (work / 'manifest.json').write_text(json.dumps({'outputs': [
        {'slot': 0, 'file': 'exec-fresh.png'}, {'slot': 1, 'error': '本图未生成'}]}))
    monkeypatch.setattr(reconcile, 'verify_provenance', verify_provenance)
    reconcile.reconcile_once(factory, store)
    job, round, attempt, count = state(recovery)
    assert job.status == round.status == 'partial'
    assert count == 1 and attempt.status == 'finished' and job.execution_count == 1
    reconcile.reconcile_once(factory, store)
    assert state(recovery)[3] == 1


def test_same_session_revision_has_current_image_in_new_work_directory(real_env, monkeypatch):
    created = frozen_request(real_env)
    cli(monkeypatch, real_env, created)
    runner.run_generation(job_for(real_env[1], created), real_env[1], real_env[2])
    client, factory, store, _ = real_env
    before = client.get('/api/v1/tasks/' + created['taskId']).json()
    response = client.post('/api/v1/tasks/' + created['taskId'] + '/rounds',
        json={'taskId': created['taskId'], 'target': 0, 'note': '改当前图片'},
        headers={'Idempotency-Key': 'same-session-revision'})
    assert response.status_code == 202, response.text
    revised = response.json()
    calls = []
    def execute(args, prompt, control, timeout, stop, start):
        calls.append(args)
        assert args[args.index('resume') + 3] == 'test-session'
        assert 'currentPath' in prompt and '/work/current/00.png' in prompt
        assert (control.parents[1] / 'rounds' / revised['roundId'] / 'current/00.png').read_bytes() == image_bytes()
        start(999, 'boot', 'birth')
        (control / 'events.jsonl').write_text(json.dumps({'type': 'thread.started', 'thread_id': 'test-session'}) + '\n')
        return {'exit_code': 1, 'reason': None}
    monkeypatch.setattr(runner, 'execute', execute)
    runner.run_generation(job_for(factory, revised), factory, store)
    assert len(calls) == 1
    after = client.get('/api/v1/tasks/' + created['taskId']).json()
    assert after['task']['state'] == '失败'
    assert after['task']['images'] == before['task']['images']
    assert after['task']['sessionId'] == before['task']['sessionId'] == 'test-session'


def test_known_prelaunch_failure_can_retry_without_replacing_an_existing_session(real_env, monkeypatch):
    from app.modules.skills.models import SkillVersionRecord
    created = frozen_request(real_env)
    with real_env[1]() as session:
        skill = session.scalar(select(SkillVersionRecord))
        original = real_env[2].objects[skill.object_key]
        real_env[2].objects[skill.object_key] = b'broken'
    calls = cli(monkeypatch, real_env, created)
    runner.run_generation(job_for(real_env[1], created), real_env[1], real_env[2])
    assert calls == []
    real_env[2].objects[skill.object_key] = original
    response = real_env[0].post('/api/v1/tasks/' + created['taskId'] + '/rounds',
        json={'taskId': created['taskId'], 'target': None, 'note': '修改文字',
              'retry': True, 'sourceRoundId': created['roundId']}, headers={'Idempotency-Key': 'safe-retry'})
    assert response.status_code == 202, response.text
    retried = response.json()
    cli(monkeypatch, real_env, retried)
    runner.run_generation(job_for(real_env[1], retried), real_env[1], real_env[2])
    detail = real_env[0].get('/api/v1/tasks/' + created['taskId']).json()
    assert detail['task']['state'] == '待查看' and detail['task']['sessionId'] == 'test-session'


def test_dispatch_keeps_original_executor_when_configuration_changes(task_env, monkeypatch):
    from app.core.config import get_settings
    from app.worker import tasks
    from app.execution import fixture_runner
    from test_tasks import submit
    receipt = submit(task_env).json()
    monkeypatch.setattr(tasks, 'session_factory', lambda: task_env[1])
    monkeypatch.setattr(get_settings(), 'enable_codex_executor', True)
    called = []
    monkeypatch.setattr(fixture_runner, 'run_generation', lambda *args: called.append('fixture'))
    monkeypatch.setattr(runner, 'run_generation', lambda *args: called.append('cli'))
    tasks.execute_job(str(job_for(task_env[1], receipt)))
    assert called == ['fixture']
