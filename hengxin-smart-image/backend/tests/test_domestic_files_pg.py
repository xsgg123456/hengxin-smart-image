"""Private attachment authorization and byte integrity using a fake object store."""
from io import BytesIO
from hashlib import sha256
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from threading import Event
from types import SimpleNamespace
from uuid import UUID
import tracemalloc

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text

from app.models import Job
from app.modules.domestic_studio import conversation_cleanup, conversation_deletion, file_service, turn_service
from app.modules.domestic_studio.archive_models import Archive, ArchiveDeletion, ArchiveFile
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion
from app.modules.domestic_studio.turn_models import OutputFile, Transcript, Turn, Upload
from app.overseas.studio.schemas import Send
from app.overseas.tasks import cleanup_files
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


class Stream(BytesIO):
    def stream(self, chunk_size):
        while chunk := self.read(chunk_size):
            yield chunk

    def release_conn(self):
        pass


class Store:
    def __init__(self):
        self.objects = {}

    def put(self, row, data):
        self.objects[(row.bucket, row.object_key)] = data

    def put_stream(self, row, stream, size):
        data = stream.read()
        assert len(data) == size
        self.put(row, data)

    def open(self, row):
        return Stream(self.objects[(row.bucket, row.object_key)])

    def stat(self, row):
        return len(self.objects[(row.bucket, row.object_key)])

    def remove(self, row):
        self.objects.pop((row.bucket, row.object_key), None)

    def keys(self, bucket, prefix):
        return [key for stored_bucket, key in self.objects if stored_bucket == bucket and key.startswith(prefix)]


def test_upload_and_read_are_private_and_integrity_checked(context, monkeypatch):
    factory, _, _, first, second, channel, _ = context
    monkeypatch.setattr(file_service, 'get_settings', lambda: SimpleNamespace(minio_bucket='private'))
    store = Store()
    item = file_service.upload(factory, store, first, 'camera', channel, b'private content', '资料.txt')
    assert item['url'].startswith('/api/v1/domestic-studio/workspaces/camera/files/')
    identity = UUID(item['id'].split(':', 1)[1])
    with factory() as session:
        assert file_service.bytes_for_owner(session, store, first, 'camera', identity) == b'private content'
        for actor, workspace in ((second, 'camera'), (first, 'case')):
            with pytest.raises(HTTPException) as error:
                file_service.find(session, actor, workspace, identity)
            assert error.value.status_code == 404
        row = session.scalar(select(Upload).where(Upload.id == identity))
        store.objects[(row.bucket, row.object_key)] = b'modified'
        with pytest.raises(HTTPException) as error:
            file_service.bytes_for_owner(session, store, first, 'camera', identity)
        assert error.value.status_code == 503


def test_upload_rejects_access_to_another_members_conversation(context, monkeypatch):
    factory, _, _, first, second, channel, _ = context
    monkeypatch.setattr(file_service, 'get_settings', lambda: SimpleNamespace(minio_bucket='private'))
    store = Store()
    with pytest.raises(HTTPException) as error:
        file_service.upload(factory, store, second, 'camera', channel, b'secret', '资料.txt')
    assert error.value.status_code == 404
    assert not store.objects


def test_large_upload_is_hashed_and_sent_without_buffering_the_file(context, tmp_path, monkeypatch):
    factory, _, _, actor, _, channel, _ = context
    monkeypatch.setattr(file_service, 'get_settings', lambda: SimpleNamespace(minio_bucket='private'))
    path = tmp_path / 'large.bin'
    block = b'x' * (1024 * 1024)
    with path.open('wb') as output:
        for _ in range(32):
            output.write(block)
    expected = sha256(block * 32).hexdigest()
    class Sink:
        def put_stream(self, row, stream, size):
            assert size == 32 * len(block) and row.checksum == expected
            digest, count = sha256(), 0
            while data := stream.read(1024 * 1024):
                count += len(data)
                digest.update(data)
            assert count == size and digest.hexdigest() == expected
    tracemalloc.start()
    try:
        with path.open('rb') as stream:
            item = file_service.upload(factory, Sink(), actor, 'camera', channel, stream, 'large.bin')
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert item['sizeBytes'] == 32 * len(block)
    assert peak < 12 * 1024 * 1024


def test_image_validation_keeps_the_caller_owned_stream_open():
    from app.overseas.studio.files import validate_stream
    from files_helpers import image_bytes
    data = image_bytes()
    stream = BytesIO(data)
    assert validate_stream(stream, len(data), 'image.png')[1] == 'image/png'
    assert not stream.closed and stream.tell() == 0


def test_slow_upload_does_not_block_another_members_stop(context, monkeypatch):
    factory, catalog, skill, first, second, channel, other_channel = context
    monkeypatch.setattr(file_service, 'get_settings', lambda: SimpleNamespace(minio_bucket='private'))
    with factory.begin() as session:
        bind(session, skill['id'])
        turn_service.send(session, second, 'camera', other_channel, Send(text='停止测试'), 'send-stop', catalog)
        turn = session.scalar(select(Turn).where(Turn.actor_id == second))
        turn_id, job_id, version = turn.id, turn.job_id, turn.version
    store, started, resume = Store(), Event(), Event()
    original_put = store.put
    def slow(row, data):
        started.set()
        if not resume.wait(10):
            raise TimeoutError('test did not release storage')
        return original_put(row, data)
    monkeypatch.setattr(store, 'put', slow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(file_service.upload, factory, store, first, 'camera', channel, '附件'.encode(), '附件.txt')
        try:
            assert started.wait(5)
            with factory.begin() as session:
                session.execute(text("SET LOCAL lock_timeout = '1500ms'"))
                turn_service.cancel(session, second, 'camera', other_channel, turn_id, version)
                assert session.get(Job, job_id).status == 'cancelled'
        finally:
            resume.set()
        assert pending.result(timeout=15)['name'] == '附件.txt'


def test_upload_db_disconnect_cannot_write_after_source_cleanup(context, database, tmp_path, monkeypatch):
    factory, _, _, actor, _, channel, _ = context
    for model in (Transcript, OutputFile, Archive, ArchiveFile, ArchiveDeletion):
        model.__table__.create(database)
    settings = SimpleNamespace(minio_bucket='private', codex_execution_root=str(tmp_path / 'execution'),
                               worker_node_name='isolated-test')
    monkeypatch.setattr(file_service, 'get_settings', lambda: settings)
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    store, started, resume, pids = Store(), Event(), Event(), []
    original_put, original_owned = store.put, file_service.owned
    def owned(session, *args, **kwargs):
        result = original_owned(session, *args, **kwargs)
        if kwargs.get('lock'):
            pids.append(session.scalar(text('select pg_backend_pid()')))
        return result
    def slow(row, data):
        started.set()
        if not resume.wait(10):
            raise TimeoutError('test did not release storage')
        return original_put(row, data)
    monkeypatch.setattr(file_service, 'owned', owned)
    monkeypatch.setattr(store, 'put', slow)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(file_service.upload, factory, store, actor, 'camera', channel, b'late bytes', 'late.txt')
        try:
            assert started.wait(5) and pids
            with factory.begin() as session:
                assert session.scalar(text('select pg_terminate_backend(:pid)'), {'pid': pids[-1]})
            with factory.begin() as session:
                conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
            cleanup = pool.submit(conversation_cleanup.process, factory, store, channel)
            with pytest.raises(FutureTimeout):
                cleanup.result(timeout=.3)
        finally:
            resume.set()
        with pytest.raises(Exception):
            pending.result(timeout=15)
        assert cleanup.result(timeout=15)
    with factory() as session:
        assert session.get(ConversationDeletion, channel).status == 'deleted'
        assert session.get(Conversation, channel) is None
    assert not any(f'/{channel}/' in key for _bucket, key in store.objects)
