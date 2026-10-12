"""Actual PostgreSQL sessions: serialization, stale identity map and atomicity."""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.overseas.auth.models import Member, MemberRole
from app.overseas.db import Base
from app.overseas.members import service
from app.overseas.members.schemas import MemberPatch


@pytest.fixture
def pg_factory():
    url = os.getenv('TEST_OVERSEAS_MEMBERS_DATABASE_URL')
    if not url:
        pytest.skip('isolated PostgreSQL URL required')
    parsed = make_url(url)
    if parsed.drivername != 'postgresql+psycopg' or not (parsed.database or '').endswith('_test'):
        pytest.fail('TEST_OVERSEAS_MEMBERS_DATABASE_URL must point to a PostgreSQL *_test database')
    schema = 'p18_' + uuid4().hex
    root = create_engine(url)
    with root.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={'options': f'-c search_path={schema} -c statement_timeout=10000'})
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()
        with root.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


def member(factory, role='super_admin'):
    with factory.begin() as session:
        value = Member(corp_id='test', provider_user_id=uuid4().hex, name='相同姓名', status='active')
        session.add(value)
        session.flush()
        session.add(MemberRole(user_id=value.id, role=role))
        return value.id


def patch(factory, actor_id, target_id, barrier=None, roles=None, version=1):
    with factory() as session:
        actor = session.get(Member, actor_id)
        if barrier:
            barrier.wait(timeout=8)
        try:
            service.patch_member(session, actor, target_id, MemberPatch(
                roles=roles or ['operator'], status='active', version=version))
            return 200
        except HTTPException as exc:
            return exc.status_code


@pytest.mark.parametrize('mutual', [False, True])
def test_two_admins_cannot_concurrently_remove_all_admins(pg_factory, mutual):
    a, b = member(pg_factory), member(pg_factory)
    barrier = Barrier(2)
    with ThreadPoolExecutor(2) as pool:
        x = pool.submit(patch, pg_factory, a, b if mutual else a, barrier)
        y = pool.submit(patch, pg_factory, b, a if mutual else b, barrier)
        result = sorted([x.result(timeout=15), y.result(timeout=15)])
    assert result == [200, 403 if mutual else 409]
    with pg_factory() as session:
        assert len(service.active_admin_ids(session)) == 1


def test_concurrent_stale_version_has_one_commit(pg_factory):
    a, b, target = member(pg_factory), member(pg_factory), member(pg_factory, 'designer')
    barrier = Barrier(2)
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(patch, pg_factory, actor, target, barrier) for actor in (a, b)]
        assert sorted(f.result(timeout=15) for f in futures) == [200, 409]
    with pg_factory() as session:
        assert session.get(Member, target).version == 2
        assert len(service.audit_entries(session, target)['items']) == 1


@pytest.mark.parametrize('disabled', [False, True])
def test_waiting_actor_reauthorized_after_lock(pg_factory, monkeypatch, disabled):
    a, b, target = member(pg_factory), member(pg_factory), member(pg_factory, 'designer')
    waiting = Event()
    original = service.lock_permissions

    def signal_wait(session):
        waiting.set()
        original(session)

    with pg_factory() as first:
        original(first)
        monkeypatch.setattr(service, 'lock_permissions', signal_wait)
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(patch, pg_factory, b, target)
            assert waiting.wait(5)
            deadline = monotonic() + 5
            while not first.scalar(text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
                                         'AND NOT granted AND objid = :key'),
                                   {'key': service.PERMISSION_LOCK & 0xFFFFFFFF}):
                assert monotonic() < deadline, 'actor did not block on PostgreSQL lock'
                sleep(0.01)
            # The waiting thread has already loaded b as active and admin.
            service.patch_member(first, first.get(Member, a), b, MemberPatch(
                roles=['operator'], status='disabled' if disabled else 'active', version=1))
            assert future.result(timeout=15) == 403
    with pg_factory() as session:
        assert session.get(Member, target).version == 1
        assert service.audit_entries(session, target)['items'] == []


def test_concurrent_bootstrap_only_one_initialization(pg_factory):
    from app.overseas.members.bootstrap import bootstrap_admins
    ids = []
    with pg_factory.begin() as session:
        for i in range(2):
            value = Member(corp_id='test', provider_user_id=str(i), name='初始化', status='pending')
            session.add(value)
            ids.append(str(i))
    barrier = Barrier(2)

    def run(target):
        with pg_factory() as session:
            barrier.wait(timeout=8)
            try:
                return bootstrap_admins(session, 'test', target)
            except ValueError:
                return 0

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(run, ids)) == [0, 1]
    with pg_factory() as session:
        assert len(service.active_admin_ids(session)) == 1
