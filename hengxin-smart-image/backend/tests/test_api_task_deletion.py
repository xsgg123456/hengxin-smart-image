"""Explicit deletion end-to-end against isolated SQL and an in-memory object store."""
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from app.models import Job, Outbox, utcnow
from app.modules.api_image_edits import deletion
from app.modules.api_image_edits.conversation_models import Conversation, ConversationEvent, ConversationTurn
from app.modules.api_image_edits.deletion_models import ApiTaskDeletion
from app.modules.api_image_edits.models import ApiAttempt, ApiDispatch, ApiFile, ApiItem, ApiOperation, ApiTask, ApiVersion
from app.modules.files.variants import ImageVariants
from app.modules.management.api_stats.models import ApiUsageFact
from app.retention.models import RetentionEntry
from files_helpers import files_env
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_versions import setup_result, post
from test_api_cli_conversation import seed_gate, cli_enabled, submit, fake_executor, run


def prepared(files_env, monkeypatch, settings, candidate=True):
    client, factory, store, _ = files_env
    task_id, item, path = setup_result(client, factory)
    fake_executor(monkeypatch, image=candidate)
    turn = submit(client, path)
    run(factory, store, turn)
    # Fake executor has no OS process; supply the same persisted exit evidence as production.
    with factory.begin() as session:
        row = session.get(ConversationTurn, UUID(turn['id']))
        row.process_identity = dict(pid=99999999, boot='test', birth='1', node=settings.worker_node_name)
        conversation_id = row.conversation_id
    monkeypatch.setattr(deletion, 'same_process', lambda *args: False)
    return task_id, item, path, turn, conversation_id


@pytest.mark.parametrize('state', ['queued', 'running', 'retry_wait', 'collecting', 'uncertain', 'unknown'])
def test_api_busy_states_refuse_without_creating_receipt(files_env, state):
    client, factory, _, _ = files_env
    task_id, item, _ = setup_result(client, factory)
    with factory.begin() as session:
        session.get(ApiItem, UUID(item['id'])).state = state
    response = client.delete(f'{ROOT}/tasks/{task_id}')
    assert response.status_code == 409, response.text
    with factory() as session:
        assert session.get(ApiTaskDeletion, UUID(task_id)) is None


@pytest.mark.parametrize('field,value', [('lease_token', uuid4()), ('lease_until', utcnow())])
def test_unconfirmed_api_lease_or_recovery_refuses(files_env, field, value):
    client, factory, _, _ = files_env
    task_id, item, _ = setup_result(client, factory)
    with factory.begin() as session:
        setattr(session.get(ApiItem, UUID(item['id'])), field, value)
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 409


@pytest.mark.parametrize('state', ['queued', 'running', 'uncertain', 'cancelling', 'unknown'])
def test_cli_busy_or_unknown_refuses(files_env, monkeypatch, cli_enabled, state):
    task_id, _, _, turn, _ = prepared(files_env, monkeypatch, cli_enabled)
    client, factory, _, _ = files_env
    with factory.begin() as session:
        session.get(ConversationTurn, UUID(turn['id'])).status = state
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 409


@pytest.mark.parametrize('evidence', ['turn_finish', 'job_finish', 'job_status', 'job_lease', 'identity'])
def test_candidate_requires_confirmed_exit(files_env, monkeypatch, cli_enabled, evidence):
    task_id, _, _, turn, _ = prepared(files_env, monkeypatch, cli_enabled)
    client, factory, _, _ = files_env
    with factory.begin() as session:
        row = session.get(ConversationTurn, UUID(turn['id']))
        job = session.get(Job, row.job_id)
        if evidence == 'turn_finish': row.finished_at = None
        if evidence == 'job_finish': job.completed_at = None
        if evidence == 'job_status': job.status = 'uncertain'
        if evidence == 'job_lease': job.lease_until = utcnow() - timedelta(days=1)
        if evidence == 'identity': row.process_identity = None
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 409


@pytest.mark.parametrize('candidate', [True, False])
def test_idle_complete_erasure_and_minimal_receipt(files_env, monkeypatch, cli_enabled, candidate):
    task_id, item, path, _, conversation_id = prepared(files_env, monkeypatch, cli_enabled, candidate)
    client, factory, store, _ = files_env
    with factory.begin() as session:
        file = session.get(ApiFile, UUID(item['source']['fileId']))
        variant = session.get(ImageVariants, ('api-image-edits', file.id))
        variant.outputs = {'256': {'checksum': 'a' * 64, 'size': 1}}
        store.objects[f'derived/api-image-edits/{file.id}/v1-256-{"a" * 64}.webp'] = b'x'
        store.objects[f'derived/api-image-edits/{file.id}/unfinished.webp'] = b'x'
    result = client.delete(f'{ROOT}/tasks/{task_id}')
    assert result.status_code == 202 and result.json()['state'] == 'deleting', result.text
    assert client.get(f'{ROOT}/tasks/{task_id}').status_code == 200
    assert post(client, path + '/conversation/turns', {'text': 'late', 'baseVersion': 1}).status_code == 409
    assert deletion.process(factory, store, task_id, cli_enabled) == 'deleted'
    assert client.get(f'{ROOT}/tasks/{task_id}/deletion').json()['state'] == 'deleted'
    assert client.delete(f'{ROOT}/tasks/{task_id}').json()['state'] == 'deleted'
    assert client.get(f'{ROOT}/tasks/{task_id}').status_code == 404
    assert not (Path(cli_enabled.codex_execution_root) / 'api-edits' / str(conversation_id)).exists()
    assert Path(cli_enabled.codex_auth_file).exists()
    assert store.objects == {}
    with factory() as session:
        for model in (ApiTask, ApiItem, ApiVersion, ApiAttempt, ApiOperation, ApiDispatch, ApiFile,
                      Conversation, ConversationTurn, ConversationEvent, Job, Outbox, RetentionEntry, ImageVariants):
            assert session.scalars(select(model)).all() == [], model.__name__
        receipt = session.get(ApiTaskDeletion, UUID(task_id))
        assert receipt.manifest == {} and receipt.error is None and receipt.completed_at
        facts = session.scalars(select(ApiUsageFact)).all()
        assert facts and all(f.task_name == '已删除任务' for f in facts)


def test_legacy_soft_deleted_tasks_not_reclaimed(files_env, cli_enabled):
    client, factory, store, _ = files_env
    task_id, _, _ = setup_result(client, factory)
    with factory.begin() as session:
        session.get(ApiTask, UUID(task_id)).deleted_at = utcnow()
    before = dict(store.objects)
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 404
    assert deletion.run_pending(factory, store, cli_enabled) == []
    assert store.objects == before


def test_shared_files_survive_and_last_task_deletes_them(files_env, cli_enabled):
    client, factory, store, _ = files_env
    first, _, _ = setup_result(client, factory)
    second, second_item, _ = setup_result(client, factory)
    with factory.begin() as session:
        a, b = session.get(ApiTask, UUID(first)), session.get(ApiTask, UUID(second))
        shared_id = a.material_id
        b.material_id = shared_id
        key = session.get(ApiFile, shared_id).object_key
    assert client.delete(f'{ROOT}/tasks/{first}').status_code == 202
    assert client.delete(f'{ROOT}/tasks/{second}').status_code == 202
    assert deletion.process(factory, store, first, cli_enabled) == 'deleted'
    assert key in store.objects
    assert deletion.process(factory, store, second, cli_enabled) == 'deleted'
    assert key not in store.objects


def test_cleanup_in_progress_refuses_delete(files_env, monkeypatch, cli_enabled):
    task_id, _, _, _, conversation_id = prepared(files_env, monkeypatch, cli_enabled)
    client, factory, _, _ = files_env
    with factory.begin() as session:
        row = session.scalar(select(RetentionEntry).where(RetentionEntry.resource_id == conversation_id))
        row.status = 'expire_pending'
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 409
