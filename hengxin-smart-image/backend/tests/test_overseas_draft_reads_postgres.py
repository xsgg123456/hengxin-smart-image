"""Actual PG snapshots/locks, with explicit barriers rather than timing races."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
from app.overseas.auth.models import Member
from app.overseas.drafts import queue, read, router, service
from app.overseas.drafts.models import RequirementDraft
from app.overseas.drafts.schemas import SaveDraft
from test_overseas_draft_postgres import seed, add_job
from test_overseas_members_postgres import pg_factory, member


def get(factory, actor_id):
    with factory() as session:
        actor = session.get(Member, actor_id)  # Authentication has already begun.
        assert session.in_transaction()
        result = router.get(actor, session)
        assert not session.in_transaction()
        return result


def record():
    return SimpleNamespace(id=uuid4(), bucket='test', object_key=uuid4().hex,
        content_type='application/pdf', size_bytes=3, checksum='a' * 64)


def test_first_get_concurrency_uses_separate_write_initialization(pg_factory, monkeypatch):
    actor_id = member(pg_factory, 'designer')
    barrier = Barrier(2)
    original = read.snapshot
    def missing_together(bind, owner_id):
        result = original(bind, owner_id)
        if result is None:
            barrier.wait(timeout=10)
        return result
    monkeypatch.setattr(read, 'snapshot', missing_together)
    with ThreadPoolExecutor(2) as pool:
        results = [f.result(timeout=15) for f in [pool.submit(get, pg_factory, actor_id),
                                                 pool.submit(get, pg_factory, actor_id)]]
    assert results[0] == results[1] and results[0]['version'] == 1
    with pg_factory() as session:
        assert session.scalar(select(func.count()).select_from(RequirementDraft)) == 1


def test_slow_get_has_no_row_locks_and_preserves_whole_snapshot(pg_factory, monkeypatch):
    actor_id, initial = seed(pg_factory)
    designer_id = member(pg_factory, 'designer')
    with pg_factory() as session:
        initial = service.save(session, session.get(Member, actor_id), SaveDraft(
            version=initial['version'], fields={'name': '旧字段', 'designerId': str(designer_id)}))
    add_job(pg_factory, actor_id)
    job = queue.claim(pg_factory)
    entered, release = Event(), Event()
    state = {}
    original = service.materials
    def pause(reader, draft):
        if reader.connection().get_execution_options().get('postgresql_readonly'):
            state.update(reader.execute(text("SELECT pg_backend_pid() AS pid, "
                "current_setting('transaction_isolation') AS isolation, "
                "current_setting('transaction_read_only') AS readonly")).mappings().one())
            entered.set()
            assert release.wait(10)
        return original(reader, draft)
    monkeypatch.setattr(service, 'materials', pause)
    with ThreadPoolExecutor(2) as pool:
        pending = pool.submit(get, pg_factory, actor_id)
        try:
            assert entered.wait(5)
            with pg_factory() as session:
                locks = session.execute(text("SELECT mode FROM pg_locks WHERE pid = :pid "
                    "AND relation IN ('overseas_members'::regclass, "
                    "'overseas_requirement_drafts'::regclass)"), {'pid': state['pid']}).scalars().all()
                assert locks and set(locks) == {'AccessShareLock'}
            def save():
                with pg_factory() as session:
                    session.get(Member, designer_id).name = '新设计师名称'
                    draft = session.scalar(select(RequirementDraft).where(RequirementDraft.owner_id == actor_id))
                    draft.source = {'sku': 'A', 'requirementId': 'new'}
                    return service.save(session, session.get(Member, actor_id), SaveDraft(
                        version=initial['version'], fields={**initial['fields'], 'name': '新字段'}))
            saved = pool.submit(save).result(timeout=3)
            assert saved['fields']['name'] == '新字段'
            assert pool.submit(queue.complete, pg_factory, job, record()).result(timeout=3)
        finally:
            release.set()
        old = pending.result(timeout=10)
    assert state['isolation'] == 'repeatable read' and state['readonly'] == 'on'
    assert old['fields']['name'] == '旧字段' and old['source'] is None
    assert old['matchedDesigner']['name'] == initial['matchedDesigner']['name']
    assert old['materials'] == [] and old['imports'][0]['state'] == 'running'
    current = get(pg_factory, actor_id)
    assert current['fields']['name'] == '新字段' and current['source']['requirementId'] == 'new'
    assert current['matchedDesigner']['name'] == '新设计师名称'
    assert len(current['materials']) == 1 and current['imports'][0]['state'] == 'ready'


def test_snapshot_pool_options_reset_and_errors_release_connections(pg_factory, monkeypatch):
    actor_id, initial = seed(pg_factory)
    engine = pg_factory.kw['bind']
    # With one checked-in physical connection, the following write must reuse it.
    get(pg_factory, actor_id)
    assert engine.pool.checkedout() == 0
    with pg_factory() as session:
        assert session.scalar(text('SHOW transaction_read_only')) == 'off'
        assert session.scalar(text('SHOW transaction_isolation')) == 'read committed'
        service.save(session, session.get(Member, actor_id), SaveDraft(
            version=initial['version'], fields={'name': '读取后写入'}))
    with pg_factory.begin() as session:
        session.get(Member, actor_id).status = 'disabled'
    with pytest.raises(HTTPException) as error:
        get(pg_factory, actor_id)
    assert error.value.status_code == 403 and engine.pool.checkedout() == 0
    with pg_factory.begin() as session:
        session.get(Member, actor_id).status = 'active'
    def fail(*args):
        raise RuntimeError('snapshot failure')
    monkeypatch.setattr(service, 'describe', fail)
    with pytest.raises(RuntimeError, match='snapshot failure'):
        get(pg_factory, actor_id)
    assert engine.pool.checkedout() == 0
