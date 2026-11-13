"""Storage timeouts must not leave late output or archive objects after deletion."""
from datetime import timedelta
from hashlib import sha256
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from minio import Minio
from sqlalchemy import select
from urllib3 import PoolManager, Timeout

from app.capacity.models import CapacityGate, CapacityReservation
from app.db.timestamps import utcnow
from app.models import Job
from app.modules.domestic_studio import (archive_deletion, archive_service, conversation_cleanup,
    conversation_deletion, delivery_capture, delivery_context, recovery_files, recovery_transport, runner, turn_service)
from app.modules.domestic_studio.archive_models import Archive, ArchiveDeletion, ArchiveFile
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion
from app.modules.domestic_studio.turn_models import OutputFile, Picture, Transcript, Turn, Upload
from app.overseas.studio.schemas import Send
from app.overseas.studio.recovery_transport import Selection
from app.overseas.tasks import cleanup_files, cleanup_process
from app.resource_models import UserRecord
from app.storage.minio_store import MinioStore
from test_domestic_archive_pg import setup_archive
from test_domestic_runner_pg import fake_cli, prepare
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


@pytest.fixture
def storage():
    endpoint = os.environ.get('TEST_DOMESTIC_MINIO_ENDPOINT')
    if not endpoint:
        pytest.skip('requires an explicitly started disposable local MinIO server')
    if endpoint != '127.0.0.1:35441':
        pytest.fail('Only the isolated local MinIO test endpoint is allowed')
    access, secret = os.environ['TEST_DOMESTIC_MINIO_ACCESS'], os.environ['TEST_DOMESTIC_MINIO_SECRET']
    client = Minio(endpoint, access_key=access, secret_key=secret, secure=False, region='us-east-1')
    bucket = 'hxstudiowrite' + uuid4().hex
    client.make_bucket(bucket)
    store = object.__new__(MinioStore)
    store.client = client
    try:
        yield store, bucket, access, secret
    finally:
        for upload in client._list_multipart_uploads(bucket).uploads:
            assert upload.object_name.startswith('domestic-studio/') and upload.upload_id
            client._abort_multipart_upload(bucket, upload.object_name, upload.upload_id)
        for item in client.list_objects(bucket, recursive=True):
            assert item.object_name.startswith('domestic-studio/')
            client.remove_object(bucket, item.object_name)
        client.remove_bucket(bucket)


class DelayedProxy:
    def __init__(self, access, secret):
        self.received, self.release, self.done = threading.Event(), threading.Event(), threading.Event()
        self.error, self.forward_status, self.requests = None, None, 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_PUT(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                owner.requests += 1
                owner.received.set()
                if not owner.release.wait(25):
                    return
                try:
                    remote = HTTPConnection('127.0.0.1', 35441, timeout=10)
                    remote.putrequest('PUT', self.path, skip_host=True, skip_accept_encoding=True)
                    for key, value in self.headers.items():
                        if key.lower() not in ('connection', 'expect'):
                            remote.putheader(key, value)
                    remote.endheaders(body)
                    response = remote.getresponse()
                    response.read()
                    owner.forward_status = response.status
                    remote.close()
                except Exception as error:
                    owner.error = str(error)
                finally:
                    owner.done.set()

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.store = object.__new__(MinioStore)
        self.store.client = Minio('127.0.0.1:' + str(self.server.server_port), access_key=access,
            secret_key=secret, secure=False, region='us-east-1',
            http_client=PoolManager(timeout=Timeout(connect=2, read=.4), retries=False))
        self.store.ensure_private = lambda *args, **kwargs: None

    def finish(self):
        self.release.set()
        assert self.done.wait(10) and self.forward_status == 200, self.error

    def close(self):
        self.release.set()
        self.done.wait(10)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)


def test_output_timeout_blocks_source_deletion_until_original_write_arrives(context, database, tmp_path, monkeypatch, storage):
    factory, catalog, skill, actor, _, channel, _ = context
    store, bucket, access, secret = storage
    for model in (CapacityGate, CapacityReservation, Transcript, OutputFile, Archive, ArchiveFile, ArchiveDeletion):
        model.__table__.create(database)
    settings = SimpleNamespace(minio_bucket=bucket, codex_execution_root=str(tmp_path / 'execution'),
                               worker_node_name='isolated')
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_process, 'group_alive', lambda _: False)
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, actor, 'camera', channel, Send(text='要求'), 'send-late', catalog)
        turn = session.scalar(select(Turn))
        job = session.get(Job, turn.job_id)
        token = uuid4()
        job.status, job.claim_token, job.lease_until = 'running', token, utcnow() + timedelta(seconds=300)
        turn.dispatched = True
        turn.process_identity = {'node': 'isolated', 'pid': 999999, 'boot': 'expired', 'birth': 'done'}
        job_id = job.id
    raw = b'late domestic output'
    result = SimpleNamespace(data=raw, checksum=sha256(raw).hexdigest(), name='result.txt',
                             content_type='text/plain', width=None, height=None)
    item = {'status': 'captured', 'target': '/work/result.txt', 'checksum': result.checksum,
            'sizeBytes': len(raw), 'name': result.name, 'contentType': result.content_type,
            'width': None, 'height': None, 'pictureId': str(uuid4())}
    summary = SimpleNamespace(final_text='completed', session_id='s1')
    monkeypatch.setattr(delivery_context, 'success', lambda _: summary)
    monkeypatch.setattr(runner, 'close_native', lambda *args: None)
    monkeypatch.setattr(delivery_capture, 'capture',
                        lambda *args: ({'ready': True}, iter([('/work/result.txt', result, item)]), []))
    proxy = DelayedProxy(access, secret)
    try:
        assert runner.deliver(factory, job_id, token, None, None, proxy.store, settings) is False
        assert proxy.received.is_set()
        with factory.begin() as session:
            assert session.get(Job, job_id).status == 'partial'
            conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
        assert conversation_cleanup.process(factory, store, channel) is False
        with factory() as session:
            assert session.get(ConversationDeletion, channel).status == 'delete_failed'
            assert session.get(Conversation, channel) is not None
        assert not list(store.client.list_objects(bucket, recursive=True))
        proxy.finish()
        assert len(list(store.client.list_objects(bucket, recursive=True))) == 1
        with factory.begin() as session:
            conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
        assert conversation_cleanup.process(factory, store, channel) is True
        assert not list(store.client.list_objects(bucket, recursive=True))
        with factory() as session:
            assert session.get(ConversationDeletion, channel).status == 'deleted'
            assert session.get(Conversation, channel) is None
    finally:
        proxy.close()


def test_archive_timeout_never_rewrites_same_key_and_can_be_deleted_after_late_write(context, database, tmp_path, monkeypatch, storage):
    factory, fake, actor, _, channel = setup_archive(context, database, monkeypatch)
    store, bucket, access, secret = storage
    for (_, key), raw in fake.objects.items():
        store.put(SimpleNamespace(bucket=bucket, object_key=key, content_type='application/octet-stream'), raw)
    with factory.begin() as session:
        for model in (Upload, Picture):
            for row in session.scalars(select(model)):
                row.bucket = bucket
        session.get(UserRecord, actor).role = 'super_admin'
        archive_id = archive_service.prepare(session, actor, 'camera', channel,
            archive_service.ArchiveInput(productName='测试'), 'archive-late').id
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'work'), minio_bucket=bucket,
                               worker_node_name='isolated')
    import app.core.config as config
    import app.storage.minio_store as store_module
    monkeypatch.setattr(config, 'get_settings', lambda: settings)
    monkeypatch.setattr(archive_deletion, 'get_settings', lambda: settings)
    proxy = DelayedProxy(access, secret)

    class SplitStore:
        def open(self, row):
            return store.open(row)

        def put_stream(self, row, stream, size):
            return proxy.store.put_stream(row, stream, size)

    message = {'id': str(uuid4()), 'operation': 'archive', 'actor_id': str(actor),
               'task_id': str(archive_id), 'conversation_id': str(channel),
               'expires_at': time.time() + 100, 'files': []}
    try:
        monkeypatch.setattr(store_module, 'get_store', lambda: SplitStore())
        with pytest.raises(Exception):
            recovery_transport.handle_native(factory, message)
        assert proxy.received.is_set() and proxy.requests == 1
        monkeypatch.setattr(store_module, 'get_store', lambda: store)
        with pytest.raises(Exception):
            recovery_transport.handle_native(factory, message)
        with factory() as session:
            assert session.get(Archive, archive_id).status == 'copy_failed'
        assert not [row for row in store.client.list_objects(bucket, recursive=True) if '/archives/' in row.object_name]
        proxy.finish()
        assert recovery_transport.handle_native(factory, message) == {'completed': True}
        with factory.begin() as session:
            assert session.get(Archive, archive_id).status == 'ready'
            archive_deletion.request(session, actor, archive_id)
        assert archive_deletion.process(factory, store, archive_id) is True
        assert not [row for row in store.client.list_objects(bucket, recursive=True) if '/archives/' in row.object_name]
        with factory() as session:
            assert session.get(ArchiveDeletion, archive_id).status == 'deleted'
            assert session.get(Archive, archive_id) is None
        assert proxy.requests == 1
    finally:
        proxy.close()


def test_manual_recovery_timeout_retains_source_until_late_write_arrives(context, database, tmp_path, monkeypatch, storage):
    store, bucket, access, secret = storage
    factory, catalog, job_id = prepare(context, database, tmp_path, monkeypatch)
    actor, channel = context[3], context[5]
    settings = runner.get_settings()
    settings.minio_bucket = bucket
    monkeypatch.setattr(runner, 'execute', fake_cli([]))
    runner.run_turn(job_id, factory, store=store, catalog=catalog)
    for model in (Archive, ArchiveFile, ArchiveDeletion):
        model.__table__.create(database)
    monkeypatch.setattr(recovery_files, 'get_settings', lambda: settings)
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_process, 'group_alive', lambda _: False)
    work = tmp_path / 'execution' / 'domestic-studio' / str(channel) / 'persistent' / 'work'
    (work / '待取回.zip').write_bytes(b'manual recovery')
    item = next(row for row in recovery_files.available(factory, actor, channel)['items']
                if row['name'] == '待取回.zip')
    selected = Selection(id=item['id'], version=item['version'])
    proxy = DelayedProxy(access, secret)

    class SplitStore:
        def open(self, row):
            return store.open(row)

        def put_stream(self, row, stream, size):
            return proxy.store.put_stream(row, stream, size)

    try:
        assert recovery_files.recover(factory, actor, channel, [selected], SplitStore())['errors']
        assert proxy.received.is_set() and proxy.requests == 1
        assert recovery_files.recover(factory, actor, channel, [selected], store)['errors']
        with factory.begin() as session:
            conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
        assert conversation_cleanup.process(factory, store, channel) is False
        with factory() as session:
            assert session.get(ConversationDeletion, channel).status == 'delete_failed'
            assert session.get(Conversation, channel) is not None
        proxy.finish()
        with factory.begin() as session:
            conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
        assert conversation_cleanup.process(factory, store, channel) is True
        assert not list(store.client.list_objects(bucket, recursive=True))
        assert proxy.requests == 1
    finally:
        proxy.close()
