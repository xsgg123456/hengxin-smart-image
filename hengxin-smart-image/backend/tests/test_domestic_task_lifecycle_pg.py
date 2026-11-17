"""Concurrent storage and task cleanup must retain their persistent fences."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.modules.domestic_studio import archive_queries, archive_service, conversation_cleanup, file_service, task_deletion, task_service
from app.modules.domestic_studio.archive_models import ArchiveFile
from app.modules.domestic_studio.conversation_models import Conversation, ConversationRequest
from app.modules.domestic_studio.task_models import Task
from app.modules.domestic_studio.task_schemas import UpdateTask
from app.overseas.studio.files import read
from app.overseas.tasks import cleanup_files
from test_domestic_archive_pg import setup_archive
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context
from test_domestic_studio_http_pg import client_env
from test_domestic_tasks_pg import HEADERS, ROOT, new, studio


def test_task_completion_and_deletion_reject_inflight_upload(client_env, monkeypatch):
    client, factory, _, _, owner, _, _, _ = client_env
    task = new(client)
    channel = client.post(studio(task) + '/conversations', json={}, headers=HEADERS).json()['conversationId']
    from app.main import app
    from app.storage.minio_store import get_store
    store = app.dependency_overrides[get_store]()
    original, entered, proceed = store.put, Event(), Event()
    def slow(row, data):
        entered.set()
        assert proceed.wait(10)
        original(row, data)
    monkeypatch.setattr(store, 'put', slow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(file_service.upload, factory, store, owner, 'camera', UUID(channel), b'actual bytes', 'source.txt')
        try:
            assert entered.wait(5)
            for operation in ('complete', 'delete'):
                with pytest.raises(HTTPException) as error, factory.begin() as session:
                    if operation == 'complete':
                        task_service.update(session, owner, UUID(task['id']), UpdateTask(version=1, completed=True), 'complete')
                    else:
                        task_deletion.request(session, owner, UUID(task['id']), 1)
                assert error.value.status_code == 409
        finally:
            proceed.set()
        assert future.result(timeout=15)['name'] == 'source.txt'
    assert client.patch(ROOT + '/' + task['id'], json={'version': 1, 'completed': True}, headers=HEADERS).status_code == 200


def test_task_delete_preserves_independent_archive_bytes_and_cleans_all_sources(context, database, monkeypatch, tmp_path):
    factory, store, owner, _, channel = setup_archive(context, database, monkeypatch)
    with factory.begin() as session:
        archive = archive_service.prepare(session, owner, 'camera', channel,
            archive_service.ArchiveInput(productName='已归档'), 'archive')
        archive_id = archive.id
        task_id = session.get(Conversation, channel).task_id
    archive_service.complete(factory, store, archive_id, owner)
    with factory() as session:
        files = list(session.scalars(select(ArchiveFile).where(ArchiveFile.archive_id == archive_id)))
        protected = {(row.bucket, row.object_key): read(store, row) for row in files}
    initial_bytes = sum(map(len, store.objects.values()))
    settings = SimpleNamespace(codex_execution_root=str(tmp_path / 'work'), minio_bucket='private', worker_node_name='test')
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: settings)
    monkeypatch.setattr(cleanup_files, 'get_settings', lambda: settings)
    source = tmp_path / 'work' / 'domestic-studio' / str(channel)
    source.mkdir(parents=True)
    (source / 'source.txt').write_bytes(b'actual local source')
    with factory.begin() as session:
        assert task_deletion.request(session, owner, task_id, 1)['status'] == 'deleting'
    assert conversation_cleanup.process(factory, store, channel)
    with factory() as session:
        assert task_deletion.dto(session, session.get(Task, task_id))['status'] == 'deleted'
        assert archive_queries.detail(session, archive_id)['productName'] == '已归档'
    assert not source.exists() and store.objects == protected
    assert initial_bytes - sum(map(len, store.objects.values())) > 0


def test_legacy_create_receipt_replayed_in_own_task_cannot_create_duplicate(client_env):
    client, factory, _, _, owner, _, channel, _ = client_env
    with factory.begin() as session:
        row = session.scalar(select(ConversationRequest).where(ConversationRequest.conversation_id == channel))
        row.target = 'camera'
        task = session.get(Conversation, channel).task_id
        key = row.key
    root = ROOT + '/' + str(task) + '/studio'
    response = client.post(root + '/conversations', json={}, headers={**HEADERS, 'Idempotency-Key': key})
    assert response.status_code == 200 and response.json()['conversationId'] == str(channel)
    assert len(response.json()['conversations']) == 1
    other = new(client)
    assert client.post(studio(other) + '/conversations', json={},
        headers={**HEADERS, 'Idempotency-Key': key}).status_code in (404, 409)
