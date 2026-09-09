"""Independent PostgreSQL connections; no in-memory lock substitutes for DB ownership."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.contracts.business import CreateTaskInput, RevisionInput
from app.models import Base, Job, Outbox
from app.modules.tasks.models import ExecutionGate, TaskRecord, RoundRecord, TaskRequest
from app.modules.tasks.service import create_task, accept_round
from app.modules.tasks.claims import claim, end, locked_execution
from app.modules.tasks.queries import detail
from app.modules.tasks.cancellations import delete_task
from app.resource_models import UserRecord, FileRecord
from test_templates_skills import add_skill


@pytest.fixture
def pg_tasks(monkeypatch):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL required for independent PostgreSQL connections')
    assert url.startswith('postgresql')
    schema = 'test_tasks_' + uuid4().hex
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(isolated)
    factory = sessionmaker(isolated, expire_on_commit=False)
    monkeypatch.setattr(get_settings(), 'enable_fixture_executor', True)
    monkeypatch.setattr(get_settings(), 'generation_concurrency', 2)
    with factory.begin() as session:
        user = UserRecord(id=uuid4(), name='甲', role='operator', status='active', identity_source='development')
        other = UserRecord(id=uuid4(), name='乙', role='designer', status='active', identity_source='development')
        session.add_all([user, other, ExecutionGate(id=1)])
        session.flush()
        file = FileRecord(id=uuid4(), owner_id=user.id, name='a.png', bucket='test', object_key=str(uuid4()),
            content_type='image/png', checksum='a'*64, size_bytes=1, width=1, height=1, status='ready')
        session.add(file)
    skill_id = add_skill(factory, mode='text')
    body = CreateTaskInput(mode='text', name='独立连接', sources=[dict(name='a', url='a', fileId=str(file.id))],
                           note='修改', skillVersionId=skill_id)
    try:
        yield factory, user, other, body
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()


def compete(fn):
    barrier = Barrier(2)
    def call(i):
        barrier.wait(timeout=10)
        return fn(i)
    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(call, range(2)))


def test_postgres_create_and_duplicate_delivery_with_capacity_two(pg_tasks):
    factory, user, _, body = pg_tasks
    def submit(_):
        with factory() as session:
            return create_task(session, user, body, 'same')
    receipts = compete(submit)
    assert receipts[0] == receipts[1]
    with factory() as session:
        assert len(session.scalars(select(TaskRecord)).all()) == 1
        assert len(session.scalars(select(TaskRequest)).all()) == 1
        assert len(session.scalars(select(Outbox)).all()) == 1
        job_id = session.get(RoundRecord, UUID(receipts[0].roundId)).job_id
    tokens = compete(lambda _: claim(factory, job_id))
    assert sum(token is not None for token in tokens) == 1
    # Ownership persists after the claiming connection has closed; reads and cancellation do not wait.
    with factory() as session:
        assert detail(session, UUID(receipts[0].taskId)).task.state == '执行中'
    with factory() as session:
        delete_task(session, user, UUID(receipts[0].taskId))
    with factory() as session:
        assert session.get(Job, job_id).execution_count == 1


def test_postgres_different_users_round_mutex_and_replay(pg_tasks):
    factory, user, other, body = pg_tasks
    with factory() as session:
        receipt = create_task(session, user, body, 'create')
        job_id = session.get(RoundRecord, UUID(receipt.roundId)).job_id
    with factory.begin() as session:
        _, round, job = locked_execution(session, job_id)
        end(session, round, job, 'succeeded')
    task_id = UUID(receipt.taskId)
    def submit(i):
        revision = RevisionInput(taskId=receipt.taskId, target=None if i == 0 else 0, note='意见')
        with factory() as session:
            try:
                return accept_round(session, [user, other][i], task_id, revision, f'round-{i}')
            except HTTPException as error:
                return error.status_code
    receipts = compete(submit)
    assert sum(r == 409 for r in receipts) == 1
    winner = next(i for i, r in enumerate(receipts) if r != 409)
    assert submit(winner) == receipts[winner]
    with factory() as session:
        assert len(session.scalars(select(RoundRecord)).all()) == 2
        assert len(session.scalars(select(Outbox)).all()) == 2


def test_postgres_global_gate_caps_distinct_jobs(pg_tasks, monkeypatch):
    factory, user, _, body = pg_tasks
    monkeypatch.setattr(get_settings(), 'generation_concurrency', 1)
    ids = []
    for i in range(2):
        with factory() as session:
            receipt = create_task(session, user, body, str(i))
            ids.append(session.get(RoundRecord, UUID(receipt.roundId)).job_id)
    tokens = compete(lambda i: claim(factory, ids[i]))
    assert sum(token is not None for token in tokens) == 1
    with factory() as session:
        assert sorted(session.scalars(select(Job.status)).all()) == ['queued', 'running']


def test_postgres_partial_unique_constraint_rejects_direct_second_round(pg_tasks):
    factory, user, _, body = pg_tasks
    with factory() as session:
        accepted = create_task(session, user, body, 'initial')
    with pytest.raises(IntegrityError):
        with factory.begin() as session:
            job = Job(kind='generation', idempotency_key=str(uuid4()), payload_hash='a'*64, value='x')
            session.add(job)
            session.flush()
            session.add(RoundRecord(task_id=UUID(accepted.taskId), job_id=job.id,
                operator_id=user.id, note='绕过服务竞争', status='uncertain', execution_config={}))
            session.flush()
