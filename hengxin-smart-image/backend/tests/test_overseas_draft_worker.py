from datetime import timedelta
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from app.db.timestamps import utcnow
from app.overseas.drafts import queue, worker
from app.overseas.drafts.models import DraftImport, DraftMaterial
from app.overseas.materials.models import Material
from test_overseas_drafts import drafts, choose, DRAFT, HEADERS, overseas


def record(job):
    return SimpleNamespace(id=uuid4(), bucket='test', object_key='test/' + uuid4().hex,
        content_type='application/octet-stream', size_bytes=job.size, checksum='a' * 64)


def test_success_keeps_form_version_and_never_reclaims_ready(drafts, monkeypatch):
    client, factory, _, _, _, store = drafts
    draft = choose(client).json()
    job = queue.claim(factory)
    def transfer(job, material, storage, progress):
        progress(95)
        material.size_bytes, material.checksum = job.size, sha256(b'x' * job.size).hexdigest()
        storage.put(material, b'x' * job.size)
    monkeypatch.setattr(worker, 'transfer', transfer)
    worker.run_job(factory, store, job)
    current = client.get(DRAFT).json()
    assert current['version'] == draft['version'] and current['fields'] == draft['fields']
    assert len(current['materials']) == 1
    assert next(row for row in current['imports'] if row['id'] == str(job.id))['state'] == 'ready'
    second = queue.claim(factory)
    assert second.id != job.id
    assert queue.claim(factory) is None


def test_failed_import_retries_three_times_then_user_retry(drafts, monkeypatch):
    client, factory, _, _, data, store = drafts
    data['list'][0]['files'] = data['list'][0]['files'][:1]
    draft = choose(client).json()
    def fail(*args):
        raise RuntimeError('https://secret?token=PRIVATE')
    monkeypatch.setattr(worker, 'transfer', fail)
    for attempt in range(3):
        job = queue.claim(factory)
        worker.run_job(factory, store, job)
        with factory.begin() as session:
            row = session.get(DraftImport, job.id)
            assert row.attempts == attempt + 1 and 'PRIVATE' not in row.error
            row.available_at = utcnow() - timedelta(seconds=1)
    assert queue.claim(factory) is None
    assert client.get(DRAFT).json()['imports'][0]['state'] == 'failed'
    retried = client.post(DRAFT + '/imports/' + str(job.id) + '/retry', headers=HEADERS).json()
    assert retried['imports'][0]['state'] == 'queued' and retried['version'] == draft['version'] + 1
    assert queue.claim(factory).attempts == 1


def test_clear_during_transfer_discards_result_and_object(drafts, monkeypatch):
    client, factory, _, _, _, store = drafts
    draft = choose(client).json()
    job = queue.claim(factory)
    def transfer(job, material, storage, progress):
        material.size_bytes, material.checksum = job.size, 'a' * 64
        storage.put(material, b'x' * job.size)
        assert client.request('DELETE', DRAFT, json={'version': draft['version']}, headers=HEADERS).status_code == 200
    monkeypatch.setattr(worker, 'transfer', transfer)
    worker.run_job(factory, store, job)
    assert store.data == {} and client.get(DRAFT).json()['materials'] == []
    with factory() as session:
        assert session.scalar(select(Material)) is None
        assert session.get(DraftImport, job.id).state == 'cancelled'


def test_expired_lease_reclaimed_and_old_worker_fenced(drafts):
    client, factory, _, _, data, _ = drafts
    data['list'][0]['files'] = data['list'][0]['files'][:1]
    choose(client)
    old = queue.claim(factory)
    with factory.begin() as session:
        session.get(DraftImport, old.id).lease_until = utcnow() - timedelta(seconds=1)
    resumed = queue.claim(factory)
    assert resumed.id == old.id and resumed.lease_token != old.lease_token
    assert queue.renew(factory, old, 80) is False
    assert queue.complete(factory, old, record(old)) is False
    assert queue.complete(factory, resumed, record(resumed)) is True
    queue.fail(factory, old, '过期工作者错误')
    with factory() as session:
        assert session.get(DraftImport, old.id).state == 'ready'
        assert len(list(session.scalars(select(Material)))) == 1


def test_worker_transfer_runs_without_open_db_transaction(drafts, monkeypatch):
    client, factory, _, _, _, store = drafts
    choose(client)
    sessions = []
    class TrackedFactory:
        def begin(self):
            session = factory()
            sessions.append(session)
            from contextlib import contextmanager
            @contextmanager
            def transaction():
                with session, session.begin():
                    yield session
            return transaction()
    tracked = TrackedFactory()
    job = queue.claim(tracked)
    def transfer(job, material, storage, progress):
        assert sessions and all(not session.in_transaction() for session in sessions)
        material.size_bytes, material.checksum = job.size, 'a' * 64
        storage.put(material, b'x' * job.size)
    monkeypatch.setattr(worker, 'transfer', transfer)
    worker.run_job(tracked, store, job)
    assert all(not session.in_transaction() for session in sessions)
    assert len(client.get(DRAFT).json()['materials']) == 1


def test_user_remove_ready_attachment_cancels_membership(drafts):
    client, factory, _, _, _, _ = drafts
    choose(client)
    job = queue.claim(factory)
    material = record(job)
    assert queue.complete(factory, job, material)
    result = client.delete(DRAFT + '/materials/' + str(material.id), headers=HEADERS)
    assert result.status_code == 200
    assert result.json()['materials'] == []
    with factory() as session:
        assert session.scalar(select(DraftMaterial)) is None
        assert session.get(Material, material.id).task_id is None
        assert session.get(DraftImport, job.id).state == 'cancelled'
