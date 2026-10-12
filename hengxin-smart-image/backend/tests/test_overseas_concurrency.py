"""Run with TEST_OVERSEAS_MEMBERS_DATABASE_URL pointing to an isolated *_test DB."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import func, select
from app.db.timestamps import utcnow
from app.overseas.execution import claims, queue
from app.overseas.execution.models import ACTIVE, ExecutionGate, ExecutionEvent, Job, JobOutbox
from app.overseas.tasks.models import Task
from test_overseas_members_postgres import pg_factory, member


@pytest.fixture
def execution(pg_factory, monkeypatch):
    monkeypatch.setattr(claims, 'get_settings', lambda: SimpleNamespace(generation_concurrency=5, job_lease_seconds=60))
    actor = member(pg_factory, 'designer')
    with pg_factory.begin() as session:
        session.add(ExecutionGate(id=1))
        task = Task(name='并发', product_name='产品', brand='品牌', platform='Amazon', market='美国',
                    created_by=actor, designer_id=actor)
        session.add(task)
        session.flush()
        return pg_factory, task.id


def add(factory, task, key, barrier=None):
    if barrier:
        barrier.wait(timeout=10)
    with factory.begin() as session:
        return queue.enqueue(session, task, 'analysis', key, {}).id


def test_twelve_workers_six_jobs_five_cluster_slots(execution):
    factory, task = execution
    ids = [add(factory, task, str(i)) for i in range(6)]
    barrier = Barrier(12)
    def run(identity):
        barrier.wait(timeout=10)
        return claims.claim(factory, identity)
    with ThreadPoolExecutor(12) as pool:
        tokens = list(pool.map(run, ids * 2))
    assert sum(bool(token) for token in tokens) == 5
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.status.in_(ACTIVE))) == 5
        assert session.scalar(select(func.sum(Job.execution_count))) == 5
    with factory.begin() as session:
        active = session.scalar(select(Job).where(Job.status == 'running'))
        active_id, token = active.id, active.claim_token
        active.lease_until = utcnow() - timedelta(seconds=1)
        waiting = session.scalar(select(Job).where(Job.status == 'queued')).id
    assert claims.sweep_expired(factory) == 1
    assert claims.claim(factory, active_id) is None
    assert claims.claim(factory, waiting) is None
    assert not claims.finish(factory, active_id, token, 'failed')
    with factory.begin() as session:
        claims.locked_job(session, active_id).process_exited = True
    assert claims.finish(factory, active_id, token, 'failed')
    assert claims.claim(factory, waiting)


def test_concurrent_dedupe_and_transaction_rollback(execution):
    factory, task = execution
    barrier = Barrier(6)
    with ThreadPoolExecutor(6) as pool:
        ids = list(pool.map(lambda _: add(factory, task, 'same', barrier), range(6)))
    assert len(set(ids)) == 1
    with pytest.raises(RuntimeError):
        with factory.begin() as session:
            queue.enqueue(session, task, 'generation', 'aborted', {})
            raise RuntimeError('fault')
    with factory() as session:
        assert [session.scalar(select(func.count()).select_from(model))
                for model in (Job, JobOutbox, ExecutionEvent)] == [1, 1, 1]


def test_admission_and_result_publication_rollback(execution):
    factory, task = execution
    identity = add(factory, task, 'publish')
    assert claims.claim(factory, identity, admission=lambda: False) is None
    token = claims.claim(factory, identity)
    with factory.begin() as session:
        claims.locked_job(session, identity).process_exited = True
    def failing_publish(session, job, result):
        session.get(Task, task).name = 'should roll back'
        session.flush()
        raise RuntimeError('publication fault')
    with pytest.raises(RuntimeError):
        claims.finish(factory, identity, token, 'succeeded', {}, publish=failing_publish)
    with factory() as session:
        assert session.get(Task, task).name == '并发'
        assert session.get(Job, identity).status == 'running'
        assert session.get(JobOutbox, identity).completed_at is None
