"""Real PostgreSQL takeover contention after an interrupted runner's capture."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.db.timestamps import utcnow
from app.overseas.auth.models import Member
from app.overseas.execution import claims, reconcile, runner
from app.overseas.execution.models import Job
from app.overseas.studio import delivery_context, delivery_recovery, delivery_job, service
from app.overseas.studio.models import Picture
from app.overseas.studio.schemas import Send
from app.overseas.tasks import cleanup_process
from app.overseas.tasks.models import ExecutionObject
from test_overseas_deletion_postgres import ready
from test_overseas_members_postgres import pg_factory
from test_overseas_tasks import overseas
from test_overseas_studio_execution import fake_runtime
from studio_receipt_regression_helpers import WorkerInterrupted, interrupted


@pytest.mark.parametrize('workers', [2, 4])
def test_competing_reconcilers_claim_one_collector_and_one_object(ready, monkeypatch, tmp_path, workers):
    factory, store, (actor_id, task_id, _) = ready
    with factory() as session:
        response = service.send(session, session.get(Member, actor_id), task_id,
                                Send(text='设计产品'), 'recovery-race')
    turn = next(row for row in response['turns'] if row['id'] == response['activeTurnId'])
    job_id = UUID(turn['jobId'])
    commands = fake_runtime((None, factory, actor_id, {'id': str(task_id)}, None, store),
                            monkeypatch, tmp_path, image_count=1)
    monkeypatch.setattr(cleanup_process, 'group_alive', lambda _job: False)
    monkeypatch.setattr(delivery_recovery, 'get_store', lambda: store)
    original_put = store.put

    # Simulate a killed worker after capture; ordinary upload failure is terminal partial.
    with monkeypatch.context() as patch:
        patch.setattr(delivery_job, 'upload', interrupted)
        with pytest.raises(WorkerInterrupted):
            runner.run(factory, job_id)
    with factory.begin() as session:
        row = session.get(Job, job_id)
        assert row.status == 'collecting' and row.execution_count == 1
        old_token = row.claim_token
        row.lease_until = utcnow() - timedelta(seconds=1)
        row.result = {**row.result, 'deliveryRetryAt': row.lease_until.isoformat()}
    claims.sweep_expired(factory)
    rendezvous, puts = Barrier(workers), []
    original_success = delivery_context.success

    def competing_success(workspace):
        result = original_success(workspace)
        # Every worker has read the same uncertain invocation before any can claim it.
        rendezvous.wait(timeout=8)
        return result

    def put(record, data):
        puts.append(record.object_key)
        original_put(record, data)

    monkeypatch.setattr(store, 'put', put)
    with monkeypatch.context() as patch:
        patch.setattr(delivery_context, 'success', competing_success)
        with ThreadPoolExecutor(workers) as pool:
            futures = [pool.submit(reconcile.reconcile_once, factory) for _ in range(workers)]
            assert [future.result(timeout=15) for future in futures] == [0] * workers
    with factory() as session:
        row = session.get(Job, job_id)
        assert row.status == 'succeeded' and row.claim_token != old_token
        assert row.execution_count == 1
        assert row.result['deliveryStatus'] == dict(state='complete', expected=1, saved=1)
        pictures = list(session.scalars(select(Picture).where(Picture.turn_id == UUID(turn['id']))))
        assert len(pictures) == 1 and store.data[pictures[0].object_key]
        assert session.scalar(select(func.count()).select_from(ExecutionObject).where(
            ExecutionObject.job_id == job_id)) == 1
    assert len(commands) == len(puts) == 1
    before = dict(store.data)
    reconcile.reconcile_once(factory)
    runner.run(factory, job_id)
    assert store.data == before and len(commands) == len(puts) == 1
