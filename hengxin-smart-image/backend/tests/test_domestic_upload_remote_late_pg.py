"""A dead API process cannot make a delayed remote PUT escape source deletion."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from urllib.parse import unquote

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.modules.domestic_studio import conversation_cleanup, conversation_deletion, file_service, queries, turn_service
from app.modules.domestic_studio.archive_models import Archive, ArchiveDeletion, ArchiveFile
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion
from app.modules.domestic_studio.turn_models import OutputFile, Transcript, Upload
from app.overseas.tasks import cleanup_files
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context


def test_deleted_only_after_a_late_remote_write_is_confirmed_and_removed(context, database, tmp_path, monkeypatch):
    factory, catalog, _, actor, _, channel, _ = context
    for model in (Transcript, OutputFile, Archive, ArchiveFile, ArchiveDeletion):
        model.__table__.create(database)
    settings = SimpleNamespace(app_env='test', minio_bucket='private', codex_execution_root=str(tmp_path / 'execution'),
                               worker_node_name='isolated-test')
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    objects, received, commit = {}, threading.Event(), threading.Event()

    class Stream(BytesIO):
        def release_conn(self):
            pass

    class Store:
        def keys(self, bucket, prefix):
            return [key for (name, key) in objects if name == bucket and key.startswith(prefix)]
        def open(self, row):
            return Stream(objects[(row.bucket, row.object_key)])
        def remove(self, row):
            objects.pop((row.bucket, row.object_key), None)
        def stat(self, row):
            return len(objects[(row.bucket, row.object_key)])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_PUT(self):
            bucket, key = unquote(self.path).lstrip('/').split('/', 1)
            data = self.rfile.read(int(self.headers['Content-Length']))
            received.set()
            if not commit.wait(15):
                return
            objects[(bucket, key)] = data
            try:
                self.send_response(200)
                self.send_header('ETag', '"e1"')
                self.send_header('Content-Length', '0')
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
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
url,schema,actor,channel,port,root=sys.argv[1:]
factory=sessionmaker(create_engine(url).execution_options(schema_translate_map={None:schema}),expire_on_commit=False)
file_service.get_settings=lambda: SimpleNamespace(app_env='test',minio_bucket='private',codex_execution_root=root)
store=object.__new__(MinioStore)
store.client=Minio('127.0.0.1:'+port,access_key='test-key',secret_key='test-secret',secure=False)
store.client._region_map['private']='us-east-1'
store.ensure_private=lambda *a,**kw: None
file_service.upload(factory,store,UUID(actor),'camera',UUID(channel),b'private process-death data','late.txt')
""", encoding='utf-8')
    url = os.environ['TEST_DOMESTIC_STUDIO_DATABASE_URL']
    schema = database.get_execution_options()['schema_translate_map'][None]
    child = subprocess.Popen([sys.executable, str(helper), url, schema, str(actor), str(channel),
                              str(server.server_port), str(settings.codex_execution_root)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        if not received.wait(10):
            if child.poll() is not None:
                raise AssertionError('uploader exited: ' + child.stderr.read().decode(errors='replace'))
            raise AssertionError('remote store did not receive the test bytes')
        child.kill()
        child.wait(timeout=5)
        with factory.begin() as session:
            pending = session.scalar(select(Upload).where(Upload.conversation_id == channel))
            assert pending and pending.status == 'uploading'
            assert session.scalar(select(Conversation).where(Conversation.id == channel))
            with pytest.raises(HTTPException) as error:
                file_service.find(session, actor, 'camera', pending.id)
            assert error.value.status_code == 404
            with pytest.raises(HTTPException) as error:
                turn_service.upload(session, channel, 'upload:' + str(pending.id))
            assert error.value.status_code == 404
            assert queries.view(session, actor, 'camera', channel, catalog=catalog)['materials'] == []
            conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
        assert conversation_cleanup.process(factory, Store(), channel) is False
        with factory() as session:
            assert session.get(ConversationDeletion, channel).status == 'delete_failed'
            assert session.get(Conversation, channel) is not None
        assert not objects
        commit.set()
        deadline = time.monotonic() + 5
        while not objects and time.monotonic() < deadline:
            time.sleep(.02)
        assert list(objects.values()) == [b'private process-death data']
        with factory.begin() as session:
            conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
        assert conversation_cleanup.process(factory, Store(), channel) is True
        with factory() as session:
            assert session.get(ConversationDeletion, channel).status == 'deleted'
            assert session.get(Conversation, channel) is None
        assert not objects
    finally:
        commit.set()
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
