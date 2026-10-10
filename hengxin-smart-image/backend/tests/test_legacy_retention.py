from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.execution import codex_runner as runner
from app.models import utcnow, Job
from app.modules.tasks.models import RoundRecord, ImageVersion
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession, ExecutionUsage
from app.retention import legacy
from app.retention.state import entry
from files_helpers import files_env  # noqa: F401
from test_codex_runner import real_env, frozen_request, cli  # noqa: F401
from test_tasks import job_for


def completed(env, monkeypatch):
    created = frozen_request(env)
    cli(monkeypatch, env, created)
    runner.run_generation(job_for(env[1], created), env[1], env[2])
    monkeypatch.setattr('app.execution.process.same_process', lambda *args: False)
    return created, UUID(created['taskId'])


def age(factory, task_id, days):
    now = utcnow()
    with factory.begin() as session:
        row = entry(session, 'legacy_cli', task_id)
        row.last_activity_at = now - timedelta(days=days)
    return now


def test_boundaries_expiry_preserves_results_and_requires_explicit_new_session(real_env, monkeypatch):
    created, task_id = completed(real_env, monkeypatch)
    client, factory, store, _ = real_env
    root = Path(get_settings().codex_execution_root)
    cache = root / str(task_id) / 'home/.codex/cache'
    cache.mkdir(parents=True)
    (cache / 'test').write_text('cache')
    now = age(factory, task_id, 1)
    assert legacy.process(factory, store, root, task_id, now - timedelta(microseconds=1)) == 'protected'
    assert legacy.process(factory, store, root, task_id, now) == 'cache_cleared'
    assert not cache.exists()
    before = client.get('/api/v1/tasks/' + str(task_id)).json()
    now = age(factory, task_id, 7)
    assert legacy.process(factory, store, root, task_id, now - timedelta(microseconds=1)) == 'protected'
    assert legacy.process(factory, store, root, task_id, now) == 'expired'
    assert not (root / str(task_id)).exists()
    after = client.get('/api/v1/tasks/' + str(task_id)).json()
    assert after['task']['images'] == before['task']['images']
    assert after['slots'] == before['slots']
    assert after['task']['retention']['status'] == 'expired'
    assert after['task']['sessionId'] is None
    materials = client.get(f'/api/v1/tasks/{task_id}/rounds/{created["roundId"]}/materials').json()
    assert any('已按 7 天保留规则清理' in message for message in materials['notices'])
    assert not any('未采集' in message or '未提交标注' in message for message in materials['notices'])
    with factory() as session:
        assert session.scalar(select(ImageVersion))
        round = session.get(RoundRecord, UUID(created['roundId']))
        assert round.note == '' and round.execution_config == {'historyExpired': True}
        attempt = session.scalar(select(ExecutionAttempt))
        assert attempt.observation is None and attempt.workspace == ''
        assert set((session.get(ExecutionUsage, attempt.id).data or {})) <= {'input_tokens', 'output_tokens'}
        counters = entry(session, 'legacy_cli', task_id).counters
    assert legacy.process(factory, store, root, task_id, now) == 'protected'
    with factory() as session:
        assert entry(session, 'legacy_cli', task_id).counters == counters
    payload = {'taskId': str(task_id), 'target': 0, 'note': '新的修改'}
    response = client.post(f'/api/v1/tasks/{task_id}/rounds', json=payload,
                           headers={'Idempotency-Key': 'expired-rejected'})
    assert response.status_code == 409
    response = client.post(f'/api/v1/tasks/{task_id}/rounds', json={**payload, 'restartExpired': True},
                           headers={'Idempotency-Key': 'expired-restart'})
    assert response.status_code == 202, response.text
    with factory() as session:
        assert session.get(ExecutionSession, task_id) is None
        assert entry(session, 'legacy_cli', task_id).status == 'active'
        assert session.get(RoundRecord, UUID(response.json()['roundId'])).base_version_id
    calls = []
    def execute(args, prompt, control, timeout, stop, start):
        calls.append(args)
        assert 'resume' not in args
        assert '/work/current/00.png' in prompt
        start(999, 'boot', 'birth')
        (control / 'events.jsonl').write_text('{"type":"thread.started","thread_id":"fresh-session"}\n')
        return {'exit_code': 1, 'reason': None}
    monkeypatch.setattr(runner, 'execute', execute)
    runner.run_generation(job_for(factory, response.json()), factory, store)
    assert len(calls) == 1
    with factory() as session:
        assert session.get(ExecutionSession, task_id).session_id == 'fresh-session'


@pytest.mark.parametrize('status', ['queued', 'running', 'collecting', 'cancelling', 'uncertain', 'unknown'])
def test_nonterminal_and_unknown_preserved(real_env, monkeypatch, status):
    created, task_id = completed(real_env, monkeypatch)
    now = age(real_env[1], task_id, 7)
    with real_env[1].begin() as session:
        session.get(RoundRecord, UUID(created['roundId'])).status = status
    assert legacy.process(real_env[1], real_env[2], get_settings().codex_execution_root, task_id, now) == 'active_execution'


def test_cleanup_failure_fences_submission_and_retries(real_env, monkeypatch):
    _, task_id = completed(real_env, monkeypatch)
    now = age(real_env[1], task_id, 7)
    original = legacy.paths.clean
    monkeypatch.setattr(legacy.paths, 'clean', lambda *a, **kw: (_ for _ in ()).throw(OSError('denied')))
    assert legacy.process(real_env[1], real_env[2], get_settings().codex_execution_root, task_id, now) == 'retry'
    response = real_env[0].post(f'/api/v1/tasks/{task_id}/rounds',
        json={'taskId': str(task_id), 'target': 0, 'note': '新修改', 'restartExpired': True},
        headers={'Idempotency-Key': 'pending-rejected'})
    assert response.status_code == 409
    monkeypatch.setattr(legacy.paths, 'clean', original)
    assert legacy.process(real_env[1], real_env[2], get_settings().codex_execution_root, task_id, now) == 'expired'


def test_unverifiable_process_preserved(real_env, monkeypatch):
    _, task_id = completed(real_env, monkeypatch)
    now = age(real_env[1], task_id, 7)
    monkeypatch.setattr('app.execution.process.same_process', lambda *a: (_ for _ in ()).throw(OSError()))
    assert legacy.process(real_env[1], real_env[2], get_settings().codex_execution_root, task_id, now) == 'active_execution'


@pytest.mark.parametrize('evidence', ['unfinished', 'lease'])
def test_terminal_with_unresolved_evidence_preserves_history(real_env, monkeypatch, evidence):
    created, task_id = completed(real_env, monkeypatch)
    now = age(real_env[1], task_id, 7)
    with real_env[1].begin() as session:
        round = session.get(RoundRecord, UUID(created['roundId']))
        if evidence == 'unfinished':
            round.finished_at = None
        else:
            session.get(Job, round.job_id).lease_until = now - timedelta(hours=1)
    directory = Path(get_settings().codex_execution_root) / str(task_id)
    assert directory.exists()
    assert legacy.process(real_env[1], real_env[2], directory.parent, task_id, now) == 'active_execution'
    assert directory.exists()


def test_legacy_idempotency_hash_unchanged_without_restart():
    import hashlib
    import json
    from app.contracts.business import RevisionInput
    from app.modules.tasks.idempotency import fingerprint
    from uuid import uuid4
    body = RevisionInput(taskId=str(uuid4()), target=None, note='原意见')
    old = body.model_dump(exclude={'restartExpired', 'baseVersionId', 'annotationFileId'})
    digest = hashlib.sha256(json.dumps(old, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()
    assert fingerprint(body) == digest
    assert fingerprint(body.model_copy(update={'restartExpired': True})) != digest
