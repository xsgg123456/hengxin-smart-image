"""Delayed PUT against an explicitly configured disposable local MinIO server."""
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import tracemalloc
from types import SimpleNamespace
from uuid import uuid4

import pytest
from minio import Minio

from app.modules.domestic_studio import conversation_cleanup, conversation_deletion
from app.modules.domestic_studio import file_service
from app.modules.domestic_studio.archive_models import Archive, ArchiveDeletion, ArchiveFile
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion
from app.modules.domestic_studio.turn_models import OutputFile, Transcript
from app.overseas.tasks import cleanup_files
from app.storage.minio_store import MinioStore
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context


@pytest.mark.skipif(not os.environ.get('TEST_DOMESTIC_MINIO_ENDPOINT'),
                    reason='requires an explicitly started disposable local MinIO server')
def test_real_minio_late_put_blocks_deletion_until_object_is_removed(context, database, tmp_path, monkeypatch):
    endpoint = os.environ['TEST_DOMESTIC_MINIO_ENDPOINT']
    if endpoint != '127.0.0.1:35441':
        pytest.fail('Only the isolated local MinIO test endpoint is allowed')
    access, secret = os.environ['TEST_DOMESTIC_MINIO_ACCESS'], os.environ['TEST_DOMESTIC_MINIO_SECRET']
    client = Minio(endpoint, access_key=access, secret_key=secret, secure=False, region='us-east-1')
    bucket = 'hxstudiolate' + uuid4().hex
    client.make_bucket(bucket)
    factory, _, _, actor, _, channel, _ = context
    for model in (Transcript, OutputFile, Archive, ArchiveFile, ArchiveDeletion):
        model.__table__.create(database)
    settings = SimpleNamespace(app_env='test', minio_bucket=bucket, codex_execution_root=str(tmp_path / 'execution'),
                               worker_node_name='isolated-test')
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    store = object.__new__(MinioStore)
    store.client = client
    received, release, forwarded = threading.Event(), threading.Event(), threading.Event()

    class Proxy(BaseHTTPRequestHandler):
        error = None
        def log_message(self, *args):
            pass
        def do_PUT(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            received.set()
            if not release.wait(20):
                return
            try:
                remote = HTTPConnection('127.0.0.1', 35441, timeout=10)
                remote.putrequest('PUT', self.path, skip_host=True, skip_accept_encoding=True)
                for key, value in self.headers.items():
                    if key.lower() not in ('connection', 'expect'):
                        remote.putheader(key, value)
                remote.endheaders(body)
                response = remote.getresponse()
                content = response.read()
                if response.status != 200:
                    raise RuntimeError('isolated MinIO rejected the proxied PUT: ' + str(response.status))
                try:
                    self.send_response(response.status)
                    self.send_header('ETag', response.getheader('ETag', '"e1"'))
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                remote.close()
            except Exception as error:
                self.server.error = str(error)
            finally:
                forwarded.set()

    server = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
    server.error = None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    helper = tmp_path / 'uploader.py'
    helper.write_text("""import sys
from types import SimpleNamespace
from uuid import UUID
from minio import Minio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.domestic_studio import file_service
from app.storage.minio_store import MinioStore
url,schema,actor,channel,port,root,bucket,access,secret=sys.argv[1:]
factory=sessionmaker(create_engine(url).execution_options(schema_translate_map={None:schema}),expire_on_commit=False)
file_service.get_settings=lambda: SimpleNamespace(app_env='test',minio_bucket=bucket,codex_execution_root=root)
store=object.__new__(MinioStore)
store.client=Minio('127.0.0.1:'+port,access_key=access,secret_key=secret,secure=False,region='us-east-1')
store.ensure_private=lambda *a,**kw: None
file_service.upload(factory,store,UUID(actor),'camera',UUID(channel),b'real minio late write','late.txt')
""", encoding='utf-8')
    schema = database.get_execution_options()['schema_translate_map'][None]
    child = subprocess.Popen([sys.executable, str(helper), os.environ['TEST_DOMESTIC_STUDIO_DATABASE_URL'],
        schema, str(actor), str(channel), str(server.server_port), str(settings.codex_execution_root),
        bucket, access, secret], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        if not received.wait(10):
            if child.poll() is not None:
                raise AssertionError('uploader exited: ' + child.stderr.read().decode(errors='replace'))
            raise AssertionError('proxy did not receive the isolated PUT')
        child.kill()
        child.wait(timeout=5)
        with factory.begin() as session:
            conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
        assert conversation_cleanup.process(factory, store, channel) is False
        with factory() as session:
            assert session.get(ConversationDeletion, channel).status == 'delete_failed'
            assert session.get(Conversation, channel) is not None
        assert not list(client.list_objects(bucket, recursive=True))
        release.set()
        assert forwarded.wait(10) and server.error is None, server.error
        assert len(list(client.list_objects(bucket, recursive=True))) == 1
        with factory.begin() as session:
            conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
        assert conversation_cleanup.process(factory, store, channel) is True
        assert not list(client.list_objects(bucket, recursive=True))
        with factory() as session:
            assert session.get(ConversationDeletion, channel).status == 'deleted'
            assert session.get(Conversation, channel) is None
    finally:
        release.set()
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        for row in client.list_objects(bucket, recursive=True):
            assert row.object_name.startswith('domestic-studio/uploads/')
            client.remove_object(bucket, row.object_name)
        client.remove_bucket(bucket)


@pytest.mark.skipif(os.environ.get('TEST_DOMESTIC_MINIO_LARGE') != '1',
                    reason='requires an explicit large-file local MinIO test')
def test_real_minio_500mb_upload_has_bounded_python_memory(context, tmp_path, monkeypatch):
    if os.environ.get('TEST_DOMESTIC_MINIO_ENDPOINT') != '127.0.0.1:35441':
        pytest.fail('Only the isolated local MinIO test endpoint is allowed')
    client = Minio('127.0.0.1:35441', access_key=os.environ['TEST_DOMESTIC_MINIO_ACCESS'],
                   secret_key=os.environ['TEST_DOMESTIC_MINIO_SECRET'], secure=False, region='us-east-1')
    bucket = 'hxstudiolarge' + uuid4().hex
    client.make_bucket(bucket)
    factory, _, _, actor, _, channel, _ = context
    settings = SimpleNamespace(app_env='test', minio_bucket=bucket, codex_execution_root=str(tmp_path / 'execution'))
    monkeypatch.setattr(file_service, 'get_settings', lambda: settings)
    store = object.__new__(MinioStore)
    store.client = client
    path = tmp_path / 'large-upload.bin'
    with path.open('wb') as output:
        output.truncate(500_000_000)
    try:
        tracemalloc.start()
        try:
            with path.open('rb') as source:
                item = file_service.upload(factory, store, actor, 'camera', channel, source, 'large.bin')
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert item['sizeBytes'] == 500_000_000
        assert peak < 128 * 1024 * 1024
        rows = list(client.list_objects(bucket, recursive=True))
        assert len(rows) == 1 and rows[0].size == 500_000_000
    finally:
        for row in client.list_objects(bucket, recursive=True):
            assert row.object_name.startswith('domestic-studio/uploads/')
            client.remove_object(bucket, row.object_name)
        client.remove_bucket(bucket)
