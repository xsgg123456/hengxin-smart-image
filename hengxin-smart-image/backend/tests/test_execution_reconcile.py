"""Recover stopped CLI outputs with real SQLite transactions and PNG validation."""
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models import Job, utcnow
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession
from app.modules.tasks.claims import claim, mark_uncertain
from app.modules.tasks.models import ImageVersion, RoundRecord, TaskRecord
from app.modules.tasks.results import publish_results
from app.worker import reconcile
from files_helpers import files_env, image_bytes  # noqa: F401
from test_tasks import task_env, submit, job_for  # noqa: F401


@pytest.fixture
def recovery(task_env, tmp_path, monkeypatch):
    receipt = submit(task_env).json()
    factory, store = task_env[1:3]
    job_id = job_for(factory, receipt)
    token = claim(factory, job_id)
    task_id, round_id = UUID(receipt['taskId']), UUID(receipt['roundId'])
    control = tmp_path / str(task_id) / 'control' / str(round_id)
    control.mkdir(parents=True)
    home = control.parent.parent / 'home' / '.codex'
    images = home / 'generated_images' / 'session-a'
    images.mkdir(parents=True)
    (images / 'fresh.png').write_bytes(image_bytes())
    (control / 'baseline.json').write_text('{}')
    (control / 'provenance.json').write_text('{}')
    (control / 'events.jsonl').write_text('\n'.join(map(json.dumps, [
        {'type': 'thread.started', 'thread_id': 'session-a'},
        {'type': 'turn.completed', 'usage': {'input_tokens': 12}},
    ])))
    monkeypatch.setattr(get_settings(), 'codex_execution_root', str(tmp_path))
    monkeypatch.setattr(get_settings(), 'worker_node_name', 'test-node')
    monkeypatch.setattr(reconcile, 'same_process', lambda *args: False)
    monkeypatch.setattr(reconcile, 'verify_provenance', lambda *args: None)
    with factory.begin() as session:
        task = session.get(TaskRecord, task_id)
        task.execution_source = 'cli'
        round, job = session.get(RoundRecord, round_id), session.get(Job, job_id)
        mark_uncertain(round, job)
        session.add(ExecutionSession(task_id=task_id, session_id='session-a'))
        attempt = ExecutionAttempt(round_id=round_id, task_id=task_id,
            operator_id=task_env[3][0], claim_token=token, node='test-node',
            workspace=str(control), cli_version='0.153.4', process_id=123,
            boot_id='boot-a', process_start='234', status='uncertain')
        session.add(attempt)
        session.flush()
        attempt_id = attempt.id
    return factory, store, job_id, token, task_id, round_id, control, attempt_id


def state(env):
    factory, _, job_id, _, _, round_id, _, attempt_id = env
    with factory() as session:
        return (session.get(Job, job_id), session.get(RoundRecord, round_id),
                session.get(ExecutionAttempt, attempt_id),
                session.scalar(select(func.count()).select_from(ImageVersion)))


def test_complete_recovery_rotates_token_without_new_invocation(recovery):
    factory, store, job_id, old_token, *_ = recovery
    reconcile.reconcile_once(factory, store)
    job, round, attempt, count = state(recovery)
    assert job.status == round.status == 'succeeded'
    assert attempt.status == 'finished' and count == 1
    assert job.execution_count == 1 and job.claim_token != old_token
    assert attempt.claim_token == job.claim_token
    assert not publish_results(factory, job_id, old_token, [])
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ExecutionAttempt)) == 1
    assert (recovery[6] / 'baseline.json').exists()


@pytest.mark.parametrize('missing', ['provenance.json', 'baseline.json', 'events.jsonl'])
def test_missing_evidence_stays_uncertain(recovery, missing):
    (recovery[6] / missing).unlink()
    reconcile.reconcile_once(recovery[0], recovery[1])
    job, round, attempt, count = state(recovery)
    assert job.status == round.status == attempt.status == 'uncertain'
    assert count == 0 and job.execution_count == 1


def test_invalid_real_image_stays_uncertain(recovery):
    (recovery[6].parent.parent / 'home/.codex/generated_images/session-a/fresh.png').write_bytes(b'fake png')
    reconcile.reconcile_once(recovery[0], recovery[1])
    assert state(recovery)[0].status == 'uncertain'
    assert state(recovery)[3] == 0


@pytest.mark.parametrize('stage', ['before', 'upload', 'publish'])
def test_cancellation_cannot_publish(recovery, monkeypatch, stage):
    factory, store, _, _, task_id, round_id, *_ = recovery
    def cancel():
        with factory.begin() as session:
            session.get(TaskRecord, task_id).deleted_at = utcnow()
            session.get(RoundRecord, round_id).cancel_requested = True
    if stage == 'before':
        cancel()
    elif stage == 'upload':
        put = store.put
        def put_cancel(*args):
            put(*args)
            cancel()
        monkeypatch.setattr(store, 'put', put_cancel)
    else:
        publish = reconcile.publish_results
        def publish_cancel(*args):
            cancel()
            return publish(*args)
        monkeypatch.setattr(reconcile, 'publish_results', publish_cancel)
    reconcile.reconcile_once(factory, store)
    job, round, _, count = state(recovery)
    assert job.status == round.status == 'cancelled' and count == 0


@pytest.mark.parametrize('identity', ['live', 'wrong-node', 'missing-start'])
def test_unproved_process_is_untouched(recovery, monkeypatch, identity):
    if identity == 'live':
        monkeypatch.setattr(reconcile, 'same_process', lambda *args: True)
    else:
        with recovery[0].begin() as session:
            attempt = session.get(ExecutionAttempt, recovery[7])
            if identity == 'wrong-node':
                attempt.node = 'other'
            else:
                attempt.process_start = None
    reconcile.reconcile_once(recovery[0], recovery[1])
    job, _, _, count = state(recovery)
    assert job.status == 'uncertain' and job.claim_token == recovery[3] and count == 0


def test_overlapping_and_repeated_sweep_publishes_once(recovery, monkeypatch):
    factory, store = recovery[:2]
    actual = reconcile.verify_provenance
    def overlapping(*args):
        reconcile.reconcile_once(factory, store)
        return actual(*args)
    monkeypatch.setattr(reconcile, 'verify_provenance', overlapping)
    reconcile.reconcile_once(factory, store)
    reconcile.reconcile_once(factory, store)
    assert state(recovery)[0].status == 'succeeded'
    assert state(recovery)[3] == 1


def test_confirmed_failure_can_finish(recovery):
    (recovery[6] / 'exit.json').write_text(json.dumps({'exit_code': 1, 'reason': None}))
    reconcile.reconcile_once(recovery[0], recovery[1])
    assert state(recovery)[0].status == 'failed'
    assert state(recovery)[3] == 0


def test_fixture_boundary_untouched(recovery):
    with recovery[0].begin() as session:
        session.get(TaskRecord, recovery[4]).execution_source = 'fixture'
    reconcile.reconcile_once(recovery[0], recovery[1])
    assert state(recovery)[0].claim_token == recovery[3]
    assert state(recovery)[0].status == 'uncertain'


def test_untrusted_provenance_stays_uncertain(recovery, monkeypatch):
    def reject(*args):
        raise ValueError('image_generation_provenance_missing')
    monkeypatch.setattr(reconcile, 'verify_provenance', reject)
    reconcile.reconcile_once(recovery[0], recovery[1])
    assert state(recovery)[0].status == 'uncertain'
    assert state(recovery)[3] == 0


def test_recovery_heartbeat_renews_rotated_lease_during_upload(recovery, monkeypatch):
    import threading
    from app.worker import leases
    renewed = threading.Event()
    real_renew = leases.renew
    tokens = []
    def observe_renew(factory, job_id, token):
        result = real_renew(factory, job_id, token)
        if result:
            tokens.append(token)
            renewed.set()
        return result
    monkeypatch.setattr(leases, 'renew', observe_renew)
    monkeypatch.setattr(get_settings(), 'job_heartbeat_seconds', .05)
    put = recovery[1].put
    def slow_put(*args):
        assert renewed.wait(2), '恢复上传期间未续租'
        return put(*args)
    monkeypatch.setattr(recovery[1], 'put', slow_put)
    reconcile.reconcile_once(recovery[0], recovery[1])
    assert state(recovery)[0].status == 'succeeded'
    assert tokens and all(token != recovery[3] for token in tokens)


def test_stale_scanned_attempt_cannot_acquire_twice(recovery):
    with recovery[0]() as session:
        scanned = session.get(ExecutionAttempt, recovery[7])
        session.expunge(scanned)
    first = reconcile._acquire(recovery[0], scanned)
    assert first is not None
    assert reconcile._acquire(recovery[0], scanned) is None
    assert state(recovery)[0].execution_count == 1
