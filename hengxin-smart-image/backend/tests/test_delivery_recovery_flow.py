"""Delivery survives storage/commit faults without another model invocation."""
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.execution import codex_runner as runner
from app.models import Job
from app.modules.tasks.attempts import ExecutionAttempt
from app.modules.tasks.models import ImageVersion
from app.resource_models import FileRecord
from app.worker import reconcile
from files_helpers import files_env  # noqa: F401
from test_codex_runner import real_env  # noqa: F401
from test_tasks import job_for
from intervention_helpers import create_set
from test_delivery_acceptance_flow import final_call


@pytest.mark.parametrize('path', ['normal', 'intervention', 'recovery'])
def test_storage_recovery_uses_frozen_bytes_and_stable_files(real_env, monkeypatch, path):
    receipt = create_set(real_env)
    calls = final_call(real_env, monkeypatch, receipt, path)
    puts = []
    store = real_env[2]
    def fail_second(record, data):
        puts.append(record.id)
        # Real object stores overwrite a key; emulate lost reply after a successful PUT.
        store.objects[record.object_key] = data
        if len(puts) == 2:
            raise OSError('put succeeded but response was lost')
    monkeypatch.setattr(store, 'put', fail_second)
    job_id = job_for(real_env[1], receipt)
    with real_env[1]() as session:
        files_before = session.scalar(select(func.count()).select_from(FileRecord))
    runner.run_generation(job_id, real_env[1], store)
    if path == 'recovery':
        reconcile.reconcile_once(real_env[1], store)
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == 'uncertain'
        assert session.get(Job, job_id).error == '图片已生成，正在保存'
        attempt = session.scalar(select(ExecutionAttempt))
        assert attempt.observation['deliveryReady'] is True
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == 0
    control = calls[-1]['control']
    # Original model outputs/logs can vanish; the validated platform snapshot suffices.
    (control / 'events.jsonl').unlink()
    (control / 'baseline.json').unlink()
    (control / 'exit.json').unlink()
    (control.parents[1] / 'rounds' / receipt['roundId'] / 'second.png').unlink()
    reconcile.reconcile_once(real_env[1], store)
    reconcile.reconcile_once(real_env[1], store)
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == 'succeeded'
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == 2
        assert session.scalar(select(func.count()).select_from(FileRecord)) == files_before + 2
    assert puts[1] == puts[2] and len(puts) == 3
    assert len(calls) == (2 if path == 'intervention' else 1)


@pytest.mark.parametrize('committed', [False, True])
def test_publication_fault_recovers_without_duplicate_versions(real_env, monkeypatch, committed):
    receipt = create_set(real_env)
    calls = final_call(real_env, monkeypatch, receipt)
    publish = runner.publish_results
    def fail(*args):
        if committed:
            assert publish(*args)
        raise OSError('database reply lost')
    monkeypatch.setattr(runner, 'publish_results', fail)
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == ('succeeded' if committed else 'uncertain')
    reconcile.reconcile_once(real_env[1], real_env[2])
    reconcile.reconcile_once(real_env[1], real_env[2])
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == 'succeeded'
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == 2
    assert len(calls) == 1


def test_cancel_pending_delivery_never_publishes(real_env, monkeypatch):
    receipt = create_set(real_env)
    calls = final_call(real_env, monkeypatch, receipt)
    monkeypatch.setattr(real_env[2], 'put', lambda *a: (_ for _ in ()).throw(OSError('offline')))
    job_id = job_for(real_env[1], receipt)
    runner.run_generation(job_id, real_env[1], real_env[2])
    assert real_env[0].delete('/api/v1/tasks/' + receipt['taskId']).status_code == 200
    reconcile.reconcile_once(real_env[1], real_env[2])
    with real_env[1]() as session:
        assert session.get(Job, job_id).status == 'cancelled'
        assert session.scalar(select(func.count()).select_from(ImageVersion)) == 0
    assert len(calls) == 1
