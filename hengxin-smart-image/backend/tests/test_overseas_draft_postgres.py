"""Real PostgreSQL evidence for CAS, lease fencing and IO lock release."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.db.timestamps import utcnow
from app.overseas.auth.models import Member
from app.overseas.drafts import service, queue, worker
from app.overseas.drafts.models import DraftImport, RequirementDraft
from app.overseas.drafts.schemas import SaveDraft
from test_overseas_members_postgres import pg_factory, member


def seed(factory):
    actor_id = member(factory, 'designer')
    with factory() as session:
        draft = service.owned(session, session.get(Member, actor_id))
        result = service.finish(session, draft)
        return actor_id, result


def add_job(factory, actor_id):
    with factory.begin() as session:
        draft = session.scalar(select(RequirementDraft).where(RequirementDraft.owner_id == actor_id))
        row = DraftImport(draft_id=draft.id, owner_id=actor_id, epoch=draft.epoch, sku='A',
            requirement_id='req', source_file_id='file', filename='test.pdf', size=3,
            kind='competitor', available_at=utcnow())
        session.add(row)


def test_two_tabs_cas_and_first_creation(pg_factory):
    actor_id = member(pg_factory, 'designer')
    barrier = Barrier(2)
    def get():
        with pg_factory() as session:
            actor = session.get(Member, actor_id)
            barrier.wait(timeout=10)
            return service.finish(session, service.owned(session, actor))
    with ThreadPoolExecutor(2) as pool:
        a, b = [future.result(timeout=15) for future in [pool.submit(get), pool.submit(get)]]
    assert a['id'] == b['id'] and a['version'] == b['version'] == 1
    def save(name):
        with pg_factory() as session:
            actor = session.get(Member, actor_id)
            barrier.wait(timeout=10)
            try:
                service.save(session, actor, SaveDraft(version=1, fields={'name': name}))
                return 200
            except HTTPException as error:
                return error.status_code
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(save, name) for name in ('一', '二')]
        assert sorted(f.result(timeout=15) for f in futures) == [200, 409]


def test_two_workers_skip_locked_and_expired_fence(pg_factory):
    actor, _ = seed(pg_factory)
    add_job(pg_factory, actor)
    barrier = Barrier(2)
    def claim():
        barrier.wait(timeout=10)
        return queue.claim(pg_factory)
    with ThreadPoolExecutor(2) as pool:
        values = [f.result(timeout=15) for f in [pool.submit(claim), pool.submit(claim)]]
    jobs = [job for job in values if job is not None]
    assert len(jobs) == 1
    old = jobs[0]
    with pg_factory.begin() as session:
        session.get(DraftImport, old.id).lease_until = utcnow() - timedelta(seconds=1)
    newer = queue.claim(pg_factory)
    assert newer.lease_token != old.lease_token
    record = SimpleNamespace(id=uuid4(), bucket='test', object_key='x', content_type='application/pdf',
                             size_bytes=3, checksum='a' * 64)
    assert queue.complete(pg_factory, old, record) is False
    assert queue.complete(pg_factory, newer, record) is True


def test_slow_transfer_does_not_block_other_tab(pg_factory, monkeypatch):
    actor, draft = seed(pg_factory)
    add_job(pg_factory, actor)
    entered, release = Event(), Event()
    job = queue.claim(pg_factory)
    def transfer(job, record, store, progress):
        entered.set()
        assert release.wait(10)
        record.size_bytes, record.checksum = 3, 'a' * 64
    monkeypatch.setattr(worker, 'transfer', transfer)
    monkeypatch.setattr(worker, 'get_settings', lambda: SimpleNamespace(minio_bucket='test'))
    with ThreadPoolExecutor(2) as pool:
        future = pool.submit(worker.run_job, pg_factory, None, job)
        try:
            assert entered.wait(5)
            def save():
                with pg_factory() as session:
                    return service.save(session, session.get(Member, actor),
                        SaveDraft(version=draft['version'], fields={'name': '下载期间正常保存'}))
            saved = pool.submit(save).result(timeout=3)
            assert saved['fields']['name'] == '下载期间正常保存'
        finally:
            release.set()
        future.result(timeout=10)
    with pg_factory() as session:
        current = session.scalar(select(RequirementDraft).where(RequirementDraft.owner_id == actor))
        assert current.fields['name'] == '下载期间正常保存'
        assert session.get(DraftImport, job.id).state == 'ready'
