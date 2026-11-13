"""Exercise a killed multipart uploader against disposable local MinIO."""
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import subprocess
import sys
import threading
from types import SimpleNamespace

from app.modules.domestic_studio import conversation_cleanup, conversation_deletion
from app.modules.domestic_studio.archive_models import Archive, ArchiveDeletion, ArchiveFile
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion
from app.modules.domestic_studio.turn_models import OutputFile, Transcript
from app.overseas.tasks import cleanup_files
from test_domestic_late_outputs_real_minio_pg import storage
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context


def test_killed_multipart_completion_blocks_deletion_until_remote_completion(context, database, tmp_path, monkeypatch, storage):
    store, bucket, access, secret = storage
    factory, _, _, actor, _, channel, _ = context
    for model in (Transcript, OutputFile, Archive, ArchiveFile, ArchiveDeletion):
        model.__table__.create(database)
    settings = SimpleNamespace(app_env='test', minio_bucket=bucket, codex_execution_root=str(tmp_path / 'execution'),
                               worker_node_name='isolated')
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    received, release, forwarded = threading.Event(), threading.Event(), threading.Event()

    class Proxy(BaseHTTPRequestHandler):
        error = None
        def log_message(self, *args):
            pass

        def forward(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            delayed = self.command == 'POST' and 'uploadId=' in self.path
            if delayed:
                received.set()
                if not release.wait(25):
                    return
            try:
                remote = HTTPConnection('127.0.0.1', 35441, timeout=15)
                remote.putrequest(self.command, self.path, skip_host=True, skip_accept_encoding=True)
                for key, value in self.headers.items():
                    if key.lower() not in ('connection', 'expect'):
                        remote.putheader(key, value)
                remote.endheaders(body)
                response = remote.getresponse()
                content = response.read()
                if delayed and response.status != 200:
                    raise RuntimeError('multipart completion failed: ' + str(response.status))
                try:
                    self.send_response(response.status)
                    for key, value in response.getheaders():
                        if key.lower() not in ('connection', 'content-length', 'transfer-encoding'):
                            self.send_header(key, value)
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                remote.close()
            except Exception as error:
                self.server.error = str(error)
            finally:
                if delayed:
                    forwarded.set()

        do_PUT = forward
        do_POST = forward

    server = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
    server.error = None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    helper = tmp_path / 'multipart_uploader.py'
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
file_service.upload(factory,store,UUID(actor),'camera',UUID(channel),b'x'*(6*1024*1024),'large.bin')
""", encoding='utf-8')
    schema = database.get_execution_options()['schema_translate_map'][None]
    child = subprocess.Popen([sys.executable, str(helper), os.environ['TEST_DOMESTIC_STUDIO_DATABASE_URL'],
        schema, str(actor), str(channel), str(server.server_port), str(settings.codex_execution_root),
        bucket, access, secret], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        if not received.wait(15):
            if child.poll() is not None:
                raise AssertionError('uploader exited: ' + child.stderr.read().decode(errors='replace'))
            raise AssertionError('proxy did not receive multipart completion')
        child.kill()
        child.wait(timeout=5)
        assert len(store.client._list_multipart_uploads(bucket).uploads) == 1
        with factory.begin() as session:
            conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
        assert conversation_cleanup.process(factory, store, channel) is False
        with factory() as session:
            assert session.get(ConversationDeletion, channel).status == 'delete_failed'
            assert session.get(Conversation, channel) is not None
        release.set()
        assert forwarded.wait(15) and server.error is None, server.error
        assert len(list(store.client.list_objects(bucket, recursive=True))) == 1
        assert not store.client._list_multipart_uploads(bucket).uploads
        with factory.begin() as session:
            conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
        assert conversation_cleanup.process(factory, store, channel) is True
        assert not list(store.client.list_objects(bucket, recursive=True))
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
        thread.join(timeout=5)
