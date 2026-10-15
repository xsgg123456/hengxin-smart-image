from datetime import timedelta
from pathlib import Path
from uuid import UUID
import pytest
from sqlalchemy import select
from app.models import utcnow
from app.modules.api_image_edits import deletion, deletion_paths, deletion_records
from app.modules.api_image_edits.deletion_models import ApiTaskDeletion
from app.modules.api_image_edits.models import ApiFile, ApiTask
from app.modules.api_image_edits.conversation_models import ConversationTurn
from app.modules.files.variants import ImageVariants
from app.retention import api
from files_helpers import files_env
from test_api_image_domain import ROOT, enabled_api
from test_api_cli_conversation import seed_gate, cli_enabled
from test_api_image_versions import setup_result, post
from test_api_task_deletion import prepared


@pytest.mark.parametrize('fault', ['objects', 'database', 'directory', 'false_success'])
def test_failure_keeps_durable_fence_and_restarts_idempotently(files_env, monkeypatch, cli_enabled, fault):
    task_id, item, path, _, identifier = prepared(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 202
    real_erase, real_clean, real_remove = deletion_records.erase, deletion_paths.clean, store.remove
    def failed(*args, **kwargs):
        raise OSError('isolated fault')
    if fault == 'objects': store.fail_remove = True
    if fault == 'database': monkeypatch.setattr(deletion_records, 'erase', failed)
    if fault == 'directory': monkeypatch.setattr(deletion_paths, 'clean', failed)
    if fault == 'false_success': monkeypatch.setattr(store, 'remove', lambda row: None)
    now = utcnow()
    assert deletion.process(factory, store, task_id, cli_enabled, now) == 'delete_failed'
    assert client.get(f'{ROOT}/tasks/{task_id}').status_code == 200
    assert client.get(f'{ROOT}/tasks/{task_id}/deletion').json()['state'] == 'failed'
    assert post(client, path + '/restore', {'version': 1}).status_code == 409
    assert post(client, path + '/conversation/turns', {'text': 'late', 'baseVersion': 1}).status_code == 409
    assert client.get(ROOT + '/files/' + item['source']['fileId']).status_code == 404
    assert api.process(factory, store, Path(cli_enabled.codex_execution_root), identifier,
                       now + timedelta(days=9)) == 'missing_or_locked'
    with factory() as session:
        row = session.get(ApiTaskDeletion, UUID(task_id))
        assert row.phase == 'prepared' and row.attempts == 1 and row.next_attempt_at
        assert session.get(ApiTask, UUID(task_id)).deleted_at is None
        assert all(f.status == 'deleting' for f in session.scalars(select(ApiFile)))
    store.fail_remove = False
    monkeypatch.setattr(store, 'remove', real_remove)
    monkeypatch.setattr(deletion_records, 'erase', real_erase)
    monkeypatch.setattr(deletion_paths, 'clean', real_clean)
    # A fresh maintenance invocation resumes from committed database state only.
    results = deletion.run_pending(factory, store, cli_enabled, now + timedelta(minutes=1))
    assert results == [{'taskId': task_id, 'status': 'deleted'}]
    assert store.objects == {}


def test_failed_explicit_retry_preserves_manifest(files_env, monkeypatch, cli_enabled):
    task_id, _, _, _, _ = prepared(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    client.delete(f'{ROOT}/tasks/{task_id}')
    store.fail_remove = True
    assert deletion.process(factory, store, task_id, cli_enabled) == 'delete_failed'
    with factory() as session:
        manifest = session.get(ApiTaskDeletion, UUID(task_id)).manifest
    assert client.delete(f'{ROOT}/tasks/{task_id}').json()['state'] == 'deleting'
    with factory() as session:
        assert session.get(ApiTaskDeletion, UUID(task_id)).manifest == manifest
    store.fail_remove = False
    assert deletion.process(factory, store, task_id, cli_enabled) == 'deleted'


@pytest.mark.parametrize('mode', ['alive', 'wrong_node', 'unverifiable'])
def test_native_worker_requires_proof_process_has_exited(files_env, monkeypatch, cli_enabled, mode):
    task_id, _, _, turn, identifier = prepared(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    if mode == 'wrong_node':
        with factory.begin() as session:
            row = session.get(ConversationTurn, UUID(turn['id']))
            row.process_identity = {**row.process_identity, 'node': 'another-node'}
    if mode == 'alive': monkeypatch.setattr(deletion, 'same_process', lambda *args: True)
    if mode == 'unverifiable':
        def unavailable(*args): raise OSError('no process identity support')
        monkeypatch.setattr(deletion, 'same_process', unavailable)
    before = dict(store.objects)
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 202
    assert deletion.process(factory, store, task_id, cli_enabled) == 'delete_failed'
    assert store.objects == before
    assert (Path(cli_enabled.codex_execution_root) / 'api-edits' / str(identifier)).exists()


def test_unresolved_thumbnail_lease_blocks_physical_deletion(files_env, cli_enabled):
    client, factory, store, _ = files_env
    task_id, item, _ = setup_result(client, factory)
    with factory.begin() as session:
        variant = session.get(ImageVariants, ('api-image-edits', UUID(item['source']['fileId'])))
        variant.lease_until = utcnow() - timedelta(days=1)
    before = dict(store.objects)
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 202
    assert deletion.process(factory, store, task_id, cli_enabled) == 'delete_failed'
    assert store.objects == before
    with factory.begin() as session:
        session.get(ImageVariants, ('api-image-edits', UUID(item['source']['fileId']))).lease_until = None
    assert deletion.process(factory, store, task_id, cli_enabled) == 'deleted'


def test_restart_with_different_root_keeps_original_material_protected(files_env, monkeypatch, cli_enabled):
    from types import SimpleNamespace
    task_id, _, _, _, identifier = prepared(files_env, monkeypatch, cli_enabled)
    client, factory, store, _ = files_env
    client.delete(f'{ROOT}/tasks/{task_id}')
    real = deletion_paths.clean
    monkeypatch.setattr(deletion_paths, 'clean', lambda *args: (_ for _ in ()).throw(OSError('offline')))
    assert deletion.process(factory, store, task_id, cli_enabled) == 'delete_failed'
    monkeypatch.setattr(deletion_paths, 'clean', real)
    changed = SimpleNamespace(**{**vars(cli_enabled), 'codex_execution_root': cli_enabled.codex_execution_root + '-new'})
    before = dict(store.objects)
    assert deletion.process(factory, store, task_id, changed) == 'delete_failed'
    assert store.objects == before
    assert (Path(cli_enabled.codex_execution_root) / 'api-edits' / str(identifier)).exists()
    assert deletion.process(factory, store, task_id, cli_enabled) == 'deleted'
