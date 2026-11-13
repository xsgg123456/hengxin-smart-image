"""Archive copies survive source deletion and remain separated from private files."""
from hashlib import sha256
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import json
import os
import time
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.models import Job, Outbox
from app.db.session import get_session
from app.main import app
from app.modules.auth.dependencies import get_identity_id
from app.modules.domestic_studio import (archive_deletion, archive_queries, archive_service, conversation_cleanup,
                                         conversation_deletion, file_service, recovery_transport, turn_service)
from app.modules.domestic_studio.archive_models import Archive, ArchiveDeletion, ArchiveFile, ArchiveRequest
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion
from app.modules.domestic_studio.conversation_service import lock_actor
from app.modules.domestic_studio.bindings import lock_admission
from app.modules.domestic_studio.turn_models import OutputFile, Picture, Transcript, Turn, Upload
from app.overseas.studio.files import read
from app.overseas.studio import recovery_transport as shared_transport
from app.overseas.studio.schemas import Send
from app.overseas.tasks import cleanup_files
from app.resource_models import UserRecord
from app.storage.minio_store import get_store
from app.storage import minio_store
from app.core import config
from files_helpers import image_bytes
from test_domestic_files_pg import Store
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


def setup_archive(context, database, monkeypatch):
    factory, catalog, skill, first, second, channel, _ = context
    for model in (Transcript, OutputFile, Archive, ArchiveFile, ArchiveRequest, ArchiveDeletion):
        model.__table__.create(database)
    monkeypatch.setattr(file_service, 'get_settings', lambda: SimpleNamespace(minio_bucket='private'))
    store = Store()
    attachment = file_service.upload(factory, store, first, 'camera', channel, '原始附件'.encode(), '资料.txt')
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, first, 'camera', channel,
                          Send(text='产品要求', attachmentIds=[attachment['id']]), 'send', catalog)
        turn = session.scalar(select(Turn))
        turn.reply = '已完成'
        session.get(Job, turn.job_id).status = 'succeeded'
        raw = image_bytes()
        picture = Picture(id=uuid4(), turn_id=turn.id, name='成品.png', content_type='image/png',
            size_bytes=len(raw), checksum=sha256(raw).hexdigest(), bucket='private',
            object_key=f'domestic-studio/outputs/{first}/camera/{channel}/{turn.id}/picture', width=8, height=6)
        store.put(picture, raw)
        session.add(picture)
    return factory, store, first, second, channel


def test_archive_copies_are_shared_and_survive_removal_of_private_source(context, database, monkeypatch, tmp_path):
    factory, store, first, second, channel = setup_archive(context, database, monkeypatch)
    body = archive_service.ArchiveInput(productName='相机配件')
    with factory.begin() as session:
        record = archive_service.prepare(session, first, 'camera', channel, body, 'archive-key')
        identity = record.id
        assert archive_service.prepare(session, first, 'camera', channel, body, 'archive-key').id == identity
        with pytest.raises(HTTPException) as error:
            file_service.find(session, second, 'camera', session.scalar(select(Upload.id)))
        assert error.value.status_code == 404
    archive_service.complete(factory, store, identity, first)
    with factory() as session:
        archived = archive_queries.detail(session, identity)
        assert archived['productName'] == '相机配件' and archived['pictureCount'] == 1
        assert archived['turns'][0]['text'] == '产品要求' and archived['turns'][0]['reply'] == '已完成'
        assert all('/archives/' in asset['url'] for asset in
                   archived['turns'][0]['attachments'] + archived['turns'][0]['pictures'])
        originals = [(row.bucket, row.object_key) for model in (Upload, Picture) for row in session.scalars(select(model))]
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'work'), minio_bucket='private',
                               worker_node_name='test-worker')
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    workspace = tmp_path / 'work' / 'domestic-studio' / str(channel)
    workspace.mkdir(parents=True)
    (workspace / 'private.txt').write_text('source')
    with factory.begin() as session:
        version = session.get(Conversation, channel).version
        with pytest.raises(HTTPException) as error:
            conversation_deletion.request(session, second, 'camera', channel, version)
        assert error.value.status_code == 404
        assert conversation_deletion.request(session, first, 'camera', channel, version)['status'] == 'deleting'
    assert conversation_cleanup.process(factory, store, channel)
    assert not workspace.exists() and all(key not in store.objects for key in originals)
    with factory() as session:
        assert session.get(Conversation, channel) is None
        assert session.get(ConversationDeletion, channel).status == 'deleted'
        result = archive_queries.detail(session, identity)
        assert result['turns'][0]['text'] == '产品要求' and result['pictureCount'] == 1
        copied = list(session.scalars(select(ArchiveFile).where(ArchiveFile.archive_id == identity)))
        assert {read(store, row) for row in copied} == {'原始附件'.encode(), image_bytes()}
        assert archive_queries.listing(session, search='相机')['total'] == 1
        with pytest.raises(HTTPException) as error:
            file_service.find(session, second, 'camera', uuid4())
        assert error.value.status_code == 404


def test_archive_rejects_replacement_and_preserves_source_if_copy_fails(context, database, monkeypatch):
    factory, store, first, _, channel = setup_archive(context, database, monkeypatch)
    with pytest.raises(HTTPException) as error:
        with factory.begin() as session:
            archive_service.prepare(session, first, 'product', channel,
                                    archive_service.ArchiveInput(productName='产品'), 'archive')
    assert error.value.status_code == 403
    original_put = store.put
    copied = []
    def fail_archive(row, data):
        if row.object_key.startswith('domestic-studio/archives/'):
            if copied:
                original_put(row, data)
                raise OSError('injected storage error')
            copied.append(row.object_key)
        original_put(row, data)
    monkeypatch.setattr(store, 'put', fail_archive)
    body = archive_service.ArchiveInput(productName='产品')
    with factory.begin() as session:
        identity = archive_service.prepare(session, first, 'camera', channel, body, 'archive').id
    with pytest.raises(HTTPException) as error:
        archive_service.complete(factory, store, identity, first)
    assert error.value.status_code == 503
    with factory() as session:
        assert session.get(Conversation, channel) is not None
        assert session.get(Archive, identity).status == 'copy_failed'
        rows = list(session.scalars(select(ArchiveFile).where(ArchiveFile.archive_id == identity)))
        assert len(rows) == 2 and {row.status for row in rows} == {'uploading'}
        assert copied[0] in {row.object_key for row in rows}
        assert archive_queries.listing(session)['total'] == 0
        assert session.scalar(select(Picture.id)) is not None
    with factory.begin() as session:
        with pytest.raises(HTTPException) as error:
            conversation_deletion.request(session, first, 'camera', channel,
                                          session.get(Conversation, channel).version)
        assert error.value.status_code == 409
    monkeypatch.setattr(store, 'put', original_put)
    with factory.begin() as session:
        assert archive_service.prepare(session, first, 'camera', channel, body, 'archive').id == identity
        with pytest.raises(HTTPException) as error:
            archive_service.prepare(session, first, 'camera', channel,
                                    archive_service.ArchiveInput(productName='新名称'), 'different')
        assert error.value.status_code == 409
        assert archive_service.prepare(session, first, 'camera', channel, body, 'new-request').id == identity
    archive_service.complete(factory, store, identity, first)
    with factory() as session:
        assert archive_queries.detail(session, identity)['pictureCount'] == 1


def test_archive_retry_does_not_duplicate_an_unconfirmed_write(context, database, monkeypatch):
    factory, store, actor, _, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        identity = archive_service.prepare(session, actor, 'camera', channel,
            archive_service.ArchiveInput(productName='测试'), 'archive-late').id
    pending, original_put = [], store.put
    def delayed(row, data):
        pending.append((SimpleNamespace(bucket=row.bucket, object_key=row.object_key), data))
        raise TimeoutError('write may still arrive')
    monkeypatch.setattr(store, 'put', delayed)
    with pytest.raises(HTTPException):
        archive_service.complete(factory, store, identity, actor)
    monkeypatch.setattr(store, 'put', lambda *_: pytest.fail('must not issue a second PUT'))
    with pytest.raises(HTTPException):
        archive_service.complete(factory, store, identity, actor)
    assert len(pending) == 1
    original_put(*pending.pop())
    monkeypatch.setattr(store, 'put', original_put)
    archive_service.complete(factory, store, identity, actor)
    with factory() as session:
        assert session.get(Archive, identity).status == 'ready'


def test_cleanup_failure_retains_receipt_and_archived_bytes_can_be_retried(context, database, monkeypatch, tmp_path):
    factory, store, first, _, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        record = archive_service.prepare(session, first, 'camera', channel,
                                         archive_service.ArchiveInput(productName='测试'), 'archive')
        archive_id = record.id
    archive_service.complete(factory, store, archive_id, first)
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'work'), minio_bucket='private',
                               worker_node_name='test-worker')
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    with factory.begin() as session:
        version = session.get(Conversation, channel).version
        conversation_deletion.request(session, first, 'camera', channel, version)
    real_remove = store.remove
    calls = []
    def fail_second(row):
        if calls:
            raise OSError('injected delete failure')
        calls.append(row.object_key)
        real_remove(row)
    monkeypatch.setattr(store, 'remove', fail_second)
    assert not conversation_cleanup.process(factory, store, channel)
    with factory.begin() as session:
        assert session.get(ConversationDeletion, channel).status == 'delete_failed'
        assert session.get(ConversationDeletion, channel).manifest['objects']
        assert archive_queries.detail(session, archive_id)['pictureCount'] == 1
        with pytest.raises(HTTPException):
            file_service.find(session, first, 'camera', session.scalar(select(Upload.id)))
        assert conversation_deletion.request(session, first, 'camera', channel, version)['status'] == 'deleting'
    monkeypatch.setattr(store, 'remove', real_remove)
    assert conversation_cleanup.process(factory, store, channel)
    with factory() as session:
        assert session.get(ConversationDeletion, channel).status == 'deleted'
        assert archive_queries.detail(session, archive_id)['pictureCount'] == 1


def test_archive_deletion_is_admin_only_and_keeps_source(context, database, monkeypatch, tmp_path):
    factory, store, first, second, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        record = archive_service.prepare(session, first, 'camera', channel,
                                         archive_service.ArchiveInput(productName='测试'), 'archive')
        identity = record.id
    archive_service.complete(factory, store, identity, first)
    monkeypatch.setattr(archive_deletion, 'get_settings', lambda: SimpleNamespace(codex_execution_root=str(tmp_path)))
    with factory.begin() as session:
        with pytest.raises(HTTPException) as error:
            archive_deletion.request(session, second, identity)
        assert error.value.status_code == 403
        session.get(UserRecord, first).role = 'super_admin'
    with factory.begin() as session:
        assert archive_deletion.request(session, first, identity)['status'] == 'deleting'
    assert archive_deletion.process(factory, store, identity)
    with factory() as session:
        assert session.get(ArchiveDeletion, identity).status == 'deleted'
        assert session.get(Archive, identity) is None
        assert session.get(Conversation, channel) is not None
        original = session.scalar(select(Upload))
        assert read(store, original) == '原始附件'.encode()


def test_archive_http_is_shared_without_exposing_originals(context, database, monkeypatch):
    factory, store, first, second, channel = setup_archive(context, database, monkeypatch)
    identity = {'id': first}
    def db():
        with factory() as session:
            yield session
    monkeypatch.setattr(store, 'stat', lambda row: len(store.objects[(row.bucket, row.object_key)]), raising=False)
    monkeypatch.setattr(recovery_transport, 'request_archive',
                        lambda actor, archive, _conversation: archive_service.complete(factory, store, archive, actor))
    app.dependency_overrides[get_session] = db
    app.dependency_overrides[get_identity_id] = lambda: identity['id']
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            root = '/api/v1/domestic-studio'
            headers = {'X-HX-Request': '1', 'Idempotency-Key': 'archive-http'}
            url = root + f'/workspaces/camera/conversations/{channel}/archive'
            first_result = client.post(url, headers=headers, json={'productName': '相机配件'})
            repeat = client.post(url, headers=headers, json={'productName': '相机配件'})
            assert first_result.status_code == repeat.status_code == 200
            result = first_result.json()
            assert repeat.json()['id'] == result['id']
            assert client.post(root + f'/workspaces/product/conversations/{channel}/archive',
                               headers=headers, json={'productName': '替换'}).status_code == 403
            with factory() as session:
                original = session.scalar(select(Upload.id))
            identity['id'] = second
            assert client.get(root + f'/workspaces/camera/files/{original}/content').status_code == 404
            assert client.get(root + '/archives').json()['total'] == 1
            shared = client.get(root + '/archives/' + result['id'])
            assert shared.status_code == 200 and shared.json()['turns'][0]['text'] == '产品要求'
            attachment = shared.json()['turns'][0]['attachments'][0]['url']
            assert client.get(attachment).content == '原始附件'.encode()
            downloaded = client.get(root + '/archives/' + result['id'] + '/download')
            assert downloaded.status_code == 200
            with ZipFile(BytesIO(downloaded.content)) as zipped:
                assert zipped.read('001.png') == image_bytes()
            assert client.get(root + f'/archives/{result["id"]}/files/{original}/content').status_code == 404
    finally:
        for dependency in (get_session, get_identity_id, get_store):
            app.dependency_overrides.pop(dependency, None)


def test_archive_queue_only_transports_metadata_and_uses_domestic_namespace(context, database, monkeypatch, tmp_path):
    factory, store, first, _, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        identity = archive_service.prepare(session, first, 'camera', channel,
            archive_service.ArchiveInput(productName='队列测试'), 'archive').id
    class MemoryRedis:
        def __init__(self):
            self.data, self.queue, self.writes, self.queue_names = {}, [], [], []
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def eval(self, _script, _count, queue, key, identifier, raw, _limit, ttl):
            self.queue_names.append(queue); self.set(key, raw, ex=ttl); self.queue.append(identifier); return 1
        def get(self, key):
            if ':response:' in key:
                recovery_transport.consume_once(factory)
            return self.data.get(key)
        def set(self, key, value, ex):
            self.data[key] = value; self.writes.append(value)
        def delete(self, key): self.data.pop(key, None)
        def lpop(self, queue):
            self.queue_names.append(queue)
            return self.queue.pop(0) if self.queue else None
    redis = MemoryRedis()
    monkeypatch.setattr(shared_transport, 'connection', lambda: redis)
    monkeypatch.setattr(minio_store, 'get_store', lambda: store)
    monkeypatch.setattr(config, 'get_settings', lambda: SimpleNamespace(codex_execution_root=str(tmp_path)))
    result = recovery_transport.request_archive(first, identity, channel)
    assert result == {'completed': True}
    assert set(redis.queue_names) == {recovery_transport.PREFIX + 'pending'}
    messages = [json.loads(value) for value in redis.writes]
    request = next(value for value in messages if 'operation' in value)
    assert request['operation'] == 'archive' and request['task_id'] == str(identity)
    assert '原始附件' not in ''.join(redis.writes)
    with factory() as session:
        assert session.get(Archive, identity).status == 'ready'


@pytest.mark.skipif(not os.environ.get('TEST_DOMESTIC_REDIS_URL'), reason='isolated Redis not configured')
def test_real_redis_queue_keeps_domestic_and_overseas_requests_separate(context, database, monkeypatch, tmp_path):
    from redis import Redis
    url = os.environ['TEST_DOMESTIC_REDIS_URL']
    factory, store, first, _, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        identity = archive_service.prepare(session, first, 'camera', channel,
            archive_service.ArchiveInput(productName='真实队列'), 'archive').id
    monkeypatch.setattr(shared_transport, 'connection', lambda: Redis.from_url(url, decode_responses=True,
                                                                              socket_timeout=1, socket_connect_timeout=1))
    monkeypatch.setattr(minio_store, 'get_store', lambda: store)
    monkeypatch.setattr(config, 'get_settings', lambda: SimpleNamespace(codex_execution_root=str(tmp_path)))
    client = Redis.from_url(url, decode_responses=True)
    sentinel = shared_transport.QUEUE
    assert client.llen(sentinel) == 0
    client.rpush(sentinel, 'isolated-overseas-sentinel')
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(recovery_transport.request_archive, first, identity, channel)
            deadline = time.monotonic() + 10
            while not pending.done() and time.monotonic() < deadline:
                if not recovery_transport.consume_once(factory):
                    time.sleep(.05)
            assert pending.result(timeout=5) == {'completed': True}
        assert client.lrange(sentinel, 0, -1) == ['isolated-overseas-sentinel']
        with factory() as session:
            assert session.get(Archive, identity).status == 'ready'
    finally:
        client.delete(sentinel)
        client.close()


@pytest.mark.parametrize('operation', ['archive', 'conversation_cleanup'])
def test_slow_storage_does_not_hold_shared_locks(context, database, monkeypatch, tmp_path, operation):
    factory, store, first, second, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        session.get(UserRecord, first).role = 'super_admin'
        identity = archive_service.prepare(session, first, 'camera', channel,
            archive_service.ArchiveInput(productName='并发测试'), 'archive').id
    if operation == 'conversation_cleanup':
        archive_service.complete(factory, store, identity, first)
        settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'work'), minio_bucket='private',
                                   worker_node_name='test-worker')
        monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
        monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
        with factory.begin() as session:
            conversation_deletion.request(session, first, 'camera', channel, session.get(Conversation, channel).version)
    started, resume = Event(), Event()
    original = store.open
    def slow(row):
        if not started.is_set():
            started.set()
            if not resume.wait(10):
                raise TimeoutError('test did not release storage')
        return original(row)
    monkeypatch.setattr(store, 'open', slow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(archive_service.complete, factory, store, identity, first) if operation == 'archive' else \
                 pool.submit(conversation_cleanup.process, factory, store, channel)
        try:
            assert started.wait(5)
            with factory.begin() as session:
                session.execute(text("SET LOCAL lock_timeout = '1500ms'"))
                lock_actor(session, second)
                lock_admission(session)
            if operation == 'conversation_cleanup':
                with factory.begin() as session:
                    with pytest.raises(HTTPException) as exc:
                        archive_deletion.request(session, first, identity)
                    assert exc.value.status_code == 409
        finally:
            resume.set()
        future.result(timeout=15)


@pytest.mark.parametrize('corruption', ['missing_row', 'wrong_kind', 'modified_snapshot'])
def test_cleanup_preserves_source_if_archive_manifest_is_incomplete(context, database, monkeypatch, tmp_path, corruption):
    factory, store, first, _, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        identity = archive_service.prepare(session, first, 'camera', channel,
            archive_service.ArchiveInput(productName='校验测试'), 'archive').id
    archive_service.complete(factory, store, identity, first)
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'work'), minio_bucket='private',
                               worker_node_name='test-worker')
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    with factory.begin() as session:
        original = session.scalar(select(Picture))
        original_key = (original.bucket, original.object_key)
        row = session.scalar(select(ArchiveFile).where(ArchiveFile.archive_id == identity, ArchiveFile.kind == 'picture'))
        if corruption == 'missing_row':
            session.delete(row)
        elif corruption == 'wrong_kind':
            row.kind = 'output'
        else:
            record = session.get(Archive, identity)
            snapshot = dict(record.snapshot)
            snapshot['turns'] = []
            record.snapshot = snapshot
        conversation_deletion.request(session, first, 'camera', channel, session.get(Conversation, channel).version)
    assert not conversation_cleanup.process(factory, store, channel)
    assert original_key in store.objects
    with factory() as session:
        assert session.get(Conversation, channel) is not None
        assert session.get(ConversationDeletion, channel).status == 'delete_failed'
