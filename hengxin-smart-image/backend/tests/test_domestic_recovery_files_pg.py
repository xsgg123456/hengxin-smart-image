"""Manual recovery uses real conversation rows and only the owned native root."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
from threading import Event
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import UUID, uuid4
import time
import tracemalloc

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.models import Job
from app.db.session import get_session
from app.main import app
from app.modules.auth.dependencies import get_identity_id
from app.modules.domestic_studio import conversation_cleanup, conversation_deletion, delivery_capture, recovery_files, recovery_transport, runner, turn_service
from app.modules.domestic_studio.archive_models import Archive, ArchiveDeletion, ArchiveFile
from app.modules.domestic_studio.bindings import lock_admission
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion
from app.modules.domestic_studio.conversation_service import lock_actor
from app.modules.domestic_studio.turn_models import OutputFile, Picture, Turn
from app.overseas.studio.recovery_transport import Selection
from app.overseas.studio.schemas import Send
from app.overseas.tasks import cleanup_files, cleanup_process
from app.storage import minio_store
from files_helpers import image_bytes
from test_domestic_files_pg import Store
from test_domestic_runner_pg import prepare, fake_cli
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context


def setup(context, database, tmp_path, monkeypatch):
    factory, catalog, job_id = prepare(context, database, tmp_path, monkeypatch)
    calls, store = [], Store()
    monkeypatch.setattr(runner, 'execute', fake_cli(calls))
    runner.run_turn(job_id, factory, store=store, catalog=catalog)
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'execution'), minio_bucket='private',
                               worker_node_name='isolated-test')
    monkeypatch.setattr(recovery_files, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_process, 'group_alive', lambda _job: False)
    channel, actor, other = context[5], context[3], context[4]
    work = tmp_path / 'execution' / 'domestic-studio' / str(channel) / 'persistent' / 'work'
    (work / '遗漏的文件.zip').write_bytes(b'private zip bytes')
    return factory, catalog, job_id, actor, other, channel, store, calls, work


def test_manual_receipt_is_private_idempotent_and_does_not_rerun_model(context, database, tmp_path, monkeypatch):
    factory, _, job_id, actor, other, channel, store, calls, work = setup(context, database, tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as exc:
        recovery_files.available(factory, other, channel)
    assert exc.value.status_code == 404
    listing = recovery_files.available(factory, actor, channel)
    item = next(row for row in listing['items'] if row['name'] == '遗漏的文件.zip')
    selected = Selection(id=item['id'], version=item['version'])
    original_put = store.put
    def lost_reply(row, data):
        original_put(row, data)
        raise OSError('response lost after storage accepted the file')
    monkeypatch.setattr(store, 'put', lost_reply)
    assert recovery_files.recover(factory, actor, channel, [selected], store)['errors']
    monkeypatch.setattr(store, 'put', original_put)
    first = recovery_files.recover(factory, actor, channel, [selected], store)
    again = recovery_files.recover(factory, actor, channel, [selected], store)
    assert first == again and first['errors'] == [] and len(first['saved']) == 1
    with factory() as session:
        row = session.get(OutputFile, UUID(first['saved'][0]['id']))
        assert store.objects[(row.bucket, row.object_key)] == b'private zip bytes'
        assert session.get(Job, job_id).execution_count == 1
        assert len(list(session.scalars(select(OutputFile)))) == 1
    assert len(calls) == 1
    (work / '遗漏的文件.zip').write_bytes(b'changed')
    assert recovery_files.recover(factory, actor, channel, [selected], store)['errors']


def test_manual_receipt_does_not_repeat_a_write_with_unknown_result(context, database, tmp_path, monkeypatch):
    factory, _, _, actor, _, channel, store, _, _ = setup(context, database, tmp_path, monkeypatch)
    item = next(row for row in recovery_files.available(factory, actor, channel)['items'] if row['name'].endswith('.zip'))
    selected = Selection(id=item['id'], version=item['version'])
    original_put, pending = store.put, []
    def delayed(row, data):
        pending.append((SimpleNamespace(bucket=row.bucket, object_key=row.object_key), data))
        raise TimeoutError('write may still arrive')
    monkeypatch.setattr(store, 'put', delayed)
    assert recovery_files.recover(factory, actor, channel, [selected], store)['errors']
    monkeypatch.setattr(store, 'put', lambda *_: pytest.fail('must not issue a second PUT'))
    assert recovery_files.recover(factory, actor, channel, [selected], store)['errors']
    assert len(pending) == 1
    original_put(*pending.pop())
    assert len(recovery_files.recover(factory, actor, channel, [selected], store)['saved']) == 1


def test_manual_receipt_streams_large_work_file_with_bounded_memory(context, database, tmp_path, monkeypatch):
    factory, _, _, actor, _, channel, _, _, work = setup(context, database, tmp_path, monkeypatch)
    path, size = work / 'large-result.bin', 64 * 1024 * 1024
    with path.open('wb') as source:
        source.truncate(size)
    item = next(row for row in recovery_files.available(factory, actor, channel)['items']
                if row['name'] == path.name)
    selected = Selection(id=item['id'], version=item['version'])
    with TemporaryDirectory(dir=tmp_path) as root:
        class DiskStore:
            def __init__(self):
                self.path = None
            def put_stream(self, row, stream, length):
                self.path = Path(root) / str(uuid4())
                total = 0
                with self.path.open('wb') as output:
                    while chunk := stream.read(1024 * 1024):
                        total += len(chunk)
                        output.write(chunk)
                assert total == length
            def open(self, row):
                class Reader:
                    def __init__(self, path):
                        self.stream = path.open('rb')
                    def read(self, count):
                        return self.stream.read(count)
                    def close(self):
                        self.stream.close()
                    def release_conn(self):
                        pass
                return Reader(self.path)
        store = DiskStore()
        tracemalloc.start()
        try:
            result = recovery_files.recover(factory, actor, channel, [selected], store)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
            path.unlink(missing_ok=True)
        assert not result['errors'] and len(result['saved']) == 1
        assert peak < 16 * 1024 * 1024 and store.path.stat().st_size == size


def test_receipt_storage_wait_does_not_block_global_gate_or_new_turn_attempt(context, database, tmp_path, monkeypatch):
    factory, catalog, _, actor, other, channel, store, _, _ = setup(context, database, tmp_path, monkeypatch)
    item = next(row for row in recovery_files.available(factory, actor, channel)['items'] if row['name'].endswith('.zip'))
    selected, started, resume = Selection(id=item['id'], version=item['version']), Event(), Event()
    original_put = store.put
    def slow(row, data):
        started.set()
        if not resume.wait(10):
            raise TimeoutError('test did not release storage')
        return original_put(row, data)
    monkeypatch.setattr(store, 'put', slow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(recovery_files.recover, factory, actor, channel, [selected], store)
        try:
            assert started.wait(5)
            with factory.begin() as session:
                session.execute(text("SET LOCAL lock_timeout = '1500ms'"))
                lock_actor(session, other)
                lock_admission(session)
            with pytest.raises(HTTPException) as exc:
                with factory.begin() as session:
                    turn_service.send(session, actor, 'camera', channel, Send(text='继续'), 'next', catalog)
            assert exc.value.status_code == 409
        finally:
            resume.set()
        assert future.result(timeout=15)['errors'] == []


def test_db_disconnect_during_receipt_cannot_leave_post_deletion_object(context, database, tmp_path, monkeypatch):
    factory, _, _, actor, _, channel, store, _, _ = setup(context, database, tmp_path, monkeypatch)
    for model in (Archive, ArchiveFile, ArchiveDeletion):
        model.__table__.create(database)
    settings = recovery_files.get_settings()
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    item = next(row for row in recovery_files.available(factory, actor, channel)['items'] if row['name'].endswith('.zip'))
    selected = Selection(id=item['id'], version=item['version'])
    pid, started, resume = [], Event(), Event()
    real_guard, real_put = recovery_files.guard, store.put
    def guard(session, *args):
        result = real_guard(session, *args)
        pid.append(session.scalar(text('select pg_backend_pid()')))
        return result
    def slow(row, data):
        started.set()
        if not resume.wait(10):
            raise TimeoutError('test did not release storage')
        return real_put(row, data)
    monkeypatch.setattr(recovery_files, 'guard', guard)
    monkeypatch.setattr(store, 'put', slow)
    with ThreadPoolExecutor(max_workers=2) as pool:
        receive = pool.submit(recovery_files.recover, factory, actor, channel, [selected], store)
        try:
            assert started.wait(5) and pid
            with factory.begin() as session:
                assert session.scalar(text('select pg_terminate_backend(:pid)'), {'pid': pid[-1]})
            with factory.begin() as session:
                conversation_deletion.request(session, actor, 'camera', channel, session.get(Conversation, channel).version)
            cleanup = pool.submit(conversation_cleanup.process, factory, store, channel)
            with pytest.raises(FutureTimeout):
                cleanup.result(timeout=.3)
        finally:
            resume.set()
        assert receive.result(timeout=15)['errors']
        assert cleanup.result(timeout=15)
    with factory() as session:
        assert session.get(ConversationDeletion, channel).status == 'deleted'
        assert session.get(Conversation, channel) is None
    assert not any(f'/{channel}/' in key for _bucket, key in store.objects)


def test_http_routes_recheck_creator_and_native_handler(context, database, tmp_path, monkeypatch):
    factory, _, _, actor, other, channel, store, _, _ = setup(context, database, tmp_path, monkeypatch)
    identity = {'id': actor}
    def db():
        with factory() as session:
            yield session
    def bridge(operation, actor_id, conversation_id, files=()):
        message = dict(id=str(uuid4()), operation=operation, actor_id=actor_id, task_id=actor_id,
                       conversation_id=conversation_id, expires_at=time.time() + 20,
                       files=[item.model_dump() for item in files])
        return recovery_transport.handle_native(factory, message)
    monkeypatch.setattr(recovery_transport, 'request', bridge)
    monkeypatch.setattr(minio_store, 'get_store', lambda: store)
    app.dependency_overrides[get_session] = db
    app.dependency_overrides[get_identity_id] = lambda: identity['id']
    try:
        with TestClient(app) as client:
            base = f'/api/v1/domestic-studio/workspaces/camera/conversations/{channel}'
            rows = client.get(base + '/recoverable-files')
            assert rows.status_code == 200
            item = next(row for row in rows.json()['items'] if row['name'].endswith('.zip'))
            response = client.post(base + '/recover-files', headers={'X-HX-Request': '1'},
                                   json={'files': [{'id': item['id'], 'version': item['version']}]})
            assert response.status_code == 200 and len(response.json()['saved']) == 1
            identity['id'] = other
            assert client.get(base + '/recoverable-files').status_code == 404
            assert client.post(base + '/recover-files', headers={'X-HX-Request': '1'},
                               json={'files': [{'id': item['id'], 'version': item['version']}]}).status_code == 404
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_identity_id, None)


def test_corrupt_one_snapshot_saves_other_and_allows_manual_original_recovery(context, database, tmp_path, monkeypatch):
    factory, catalog, job_id = prepare(context, database, tmp_path, monkeypatch)
    calls, store = [], Store()
    def fake_two(_command, prompt, control, _timeout, monitor, started):
        import json
        calls.append(prompt)
        started(123, 'boot-id', 'birth-id')
        work = control.parents[1] / 'persistent' / 'work'
        for name in ('one.png', 'two.png'):
            (work / name).write_bytes(image_bytes())
        events = [dict(type='thread.started', thread_id='session-1'),
                  dict(type='item.completed', item=dict(id='reply', type='agent_message',
                       text='![一](/work/one.png) ![二](/work/two.png)')),
                  dict(type='turn.completed')]
        (control / 'events.jsonl').write_text('\n'.join(json.dumps(row, ensure_ascii=False) for row in events) + '\n', encoding='utf-8')
        (control / 'exit.json').write_text('{"exit_code": 0, "reason": null}', encoding='utf-8')
        assert not monitor()
        return {'exit_code': 0, 'reason': None}
    real_capture = delivery_capture.capture
    def damaged(workspace, summary, owner):
        manifest, files, issues = real_capture(workspace, summary, owner)
        (workspace.control / 'delivery' / manifest['items'][0]['snapshot']).write_bytes(b'corrupt')
        return manifest, files, issues
    monkeypatch.setattr(runner, 'execute', fake_two)
    monkeypatch.setattr(delivery_capture, 'capture', damaged)
    runner.run_turn(job_id, factory, store=store, catalog=catalog)
    with factory() as session:
        job = session.get(Job, job_id)
        turn = session.scalar(select(Turn))
        pictures = list(session.scalars(select(Picture)))
        assert job.status == 'partial' and job.execution_count == 1 and len(pictures) == 1
        assert pictures[0].source_path == '/work/two.png' and '取回文件' in turn.error
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'execution'), minio_bucket='private', worker_node_name='isolated-test')
    monkeypatch.setattr(recovery_files, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_process, 'group_alive', lambda _job: False)
    actor, channel = context[3], context[5]
    rows = recovery_files.available(factory, actor, channel)
    item = next(row for row in rows['items'] if row['source'] == 'work' and row['path'] == '/work/one.png')
    result = recovery_files.recover(factory, actor, channel, [Selection(id=item['id'], version=item['version'])], store)
    assert result['errors'] == [] and len(result['saved']) == 1 and len(calls) == 1
    with factory() as session:
        assert len(list(session.scalars(select(Picture)))) == 2
