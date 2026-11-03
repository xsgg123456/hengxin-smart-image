"""HTTP contracts only; PostgreSQL concurrency lives in the *_postgres tests."""
import pytest
from sqlalchemy import delete, event, func, select
from app.overseas.auth.dependencies import get_current_member
from app.overseas.auth.models import Member, MemberRole
from app.overseas.drafts import read, service
from app.overseas.drafts.models import RequirementDraft
from test_overseas_drafts import drafts, overseas, DRAFT
from test_overseas_tasks import add_member


def test_existing_get_uses_only_select_and_never_write_owner(drafts, monkeypatch):
    client, factory, _, _, _, _ = drafts
    first = client.get(DRAFT).json()
    def forbidden(*args):
        pytest.fail('existing GET used the write-lock entry point')
    monkeypatch.setattr(service, 'owned', forbidden)
    statements = []
    engine = factory.kw['bind']
    def capture(conn, cursor, statement, parameters, context, many):
        statements.append(statement.upper())
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        response = client.get(DRAFT)
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert response.status_code == 200 and response.json() == first
    assert statements and all(sql.lstrip().startswith('SELECT') for sql in statements)
    assert all('FOR UPDATE' not in sql for sql in statements)


def test_first_get_initializes_once_and_returns_only_current_owner(drafts):
    client, factory, actor, _, _, _ = drafts
    other = add_member(factory)
    with factory() as session:
        foreign = service.owned(session, session.get(Member, other))
        foreign.fields = {'name': '其他账号私有字段'}
        service.finish(session, foreign)
    first = client.get(DRAFT)
    assert first.status_code == 200 and first.json()['fields']['name'] == ''
    assert client.get(DRAFT).json() == first.json()
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RequirementDraft)) == 2
        mine = session.scalar(select(RequirementDraft).where(RequirementDraft.owner_id == actor))
        assert str(mine.epoch) == first.json()['id']


@pytest.mark.parametrize('change', ['disabled', 'roleless', 'missing'])
def test_snapshot_rechecks_cached_authenticated_actor(drafts, change):
    client, factory, actor_id, _, _, _ = drafts
    with factory() as session:
        cached_actor = session.get(Member, actor_id)
        session.expunge(cached_actor)
    with factory.begin() as session:
        if change == 'disabled':
            session.get(Member, actor_id).status = 'disabled'
        else:
            session.execute(delete(MemberRole).where(MemberRole.user_id == actor_id))
            if change == 'missing':
                session.delete(session.get(Member, actor_id))
    client.app.dependency_overrides[get_current_member] = lambda: cached_actor
    try:
        assert client.get(DRAFT).status_code == 403
    finally:
        client.app.dependency_overrides.pop(get_current_member)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RequirementDraft)) == 0


def test_snapshot_failure_closes_read_session_and_can_retry(drafts, monkeypatch):
    client, factory, actor_id, _, _, _ = drafts
    client.get(DRAFT)
    original = service.describe
    captured = []
    def fail(reader, draft):
        captured.append(reader)
        raise RuntimeError('description failed')
    monkeypatch.setattr(service, 'describe', fail)
    with factory() as session, pytest.raises(RuntimeError, match='description failed'):
        read.get(session, session.get(Member, actor_id))
    assert len(captured) == 1 and not captured[0].in_transaction()
    monkeypatch.setattr(service, 'describe', original)
    assert client.get(DRAFT).status_code == 200
