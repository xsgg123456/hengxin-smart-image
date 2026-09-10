"""Real HTTP acceptance using independent PostgreSQL connections."""
from uuid import UUID
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.db.session import get_session
from app.modules.auth.dependencies import get_identity_id
from app.modules.revisions.router import router
from app.modules.tasks.service import create_task
from app.modules.tasks.models import RoundRecord
from app.models import Outbox
from test_tasks_concurrency import pg_tasks, compete


def prepare(env):
    factory, user, other, body = env
    with factory() as session:
        receipt = create_task(session, user, body, 'initial')
    with factory.begin() as session:
        session.get(RoundRecord, UUID(receipt.roundId)).status = 'failed'
    app = FastAPI()
    app.include_router(router)

    def database():
        with factory() as session:
            yield session

    def identity(x_user: str = Header()):
        return UUID(x_user)

    app.dependency_overrides[get_session] = database
    app.dependency_overrides[get_identity_id] = identity
    return app, receipt


def test_http_postgres_cross_user_retry_and_revision_mutex(pg_tasks):
    factory, user, other, _ = pg_tasks
    app, initial = prepare(pg_tasks)
    def submit(i):
        data = dict(taskId=initial.taskId, target=None if i else 0, note='意见')
        if i:
            data.update(retry=True, sourceRoundId=initial.roundId, note='修改')
        with TestClient(app) as client:
            return client.post(f'/tasks/{initial.taskId}/rounds', json=data,
                headers={'Idempotency-Key': str(i), 'X-User': str([user, other][i].id)})
    responses = compete(submit)
    assert sorted(r.status_code for r in responses) == [202, 409]
    winner = next(i for i, r in enumerate(responses) if r.status_code == 202)
    assert submit(winner).json() == responses[winner].json()
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RoundRecord)) == 2
        assert session.scalar(select(func.count()).select_from(Outbox)) == 2
        assert session.get(RoundRecord, UUID(responses[winner].json()['roundId'])).operator_id == [user, other][winner].id


def test_http_postgres_same_key_returns_one_receipt(pg_tasks):
    factory, user, _, _ = pg_tasks
    app, initial = prepare(pg_tasks)
    def submit(_):
        with TestClient(app) as client:
            return client.post(f'/tasks/{initial.taskId}/rounds',
                json=dict(taskId=initial.taskId, target=None, note='意见'),
                headers={'Idempotency-Key': 'same', 'X-User': str(user.id)})
    responses = compete(submit)
    assert [r.status_code for r in responses] == [202, 202]
    assert responses[0].json() == responses[1].json()
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RoundRecord)) == 2
