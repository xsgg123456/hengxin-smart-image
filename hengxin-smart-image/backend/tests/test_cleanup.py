from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models import Job, utcnow
from app.modules.archives.models import ArchiveImage, ArchiveRecord
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession
from app.modules.tasks.models import ImageVersion, ResultSlotRecord, RoundRecord, TaskRecord, TaskSource
from app.modules.tasks.service import create_task
from app.modules.templates.models import TemplateImageRecord, TemplateRecord, TemplateVersionRecord
from app.resource_models import FileRecord
from app.worker.cleanup import CleanupPolicy, cleanup_file, cleanup_pending_object, cleanup_session, _safe_directory
from app.worker.cleanup_models import CleanupObject
from files_helpers import MemoryStore, files_env
from test_tasks_concurrency import pg_tasks


POLICY = CleanupPolicy(file_cutoff=utcnow(), session_cutoff=utcnow())
OLD = utcnow() - timedelta(days=90)


def orphan(factory, user, status='failed'):
    with factory.begin() as session:
        record = FileRecord(owner_id=user.id, name='orphan.png', bucket='test', object_key=uuid4().hex,
            content_type='image/png', checksum='a'*64, size_bytes=1, width=1, height=1,
            status=status, created_at=OLD, updated_at=OLD)
        session.add(record)
        session.flush()
        return record.id, record.object_key


def task_setup(env, tmp_path, deleted=True, status='cancelled'):
    factory, user, _, body = env
    with factory() as session:
        receipt = create_task(session, user, body, uuid4().hex)
    task_id = UUID(receipt.taskId)
    with factory.begin() as session:
        task = session.get(TaskRecord, task_id)
        task.deleted_at = OLD if deleted else None
        round = session.get(RoundRecord, UUID(receipt.roundId))
        round.status = session.get(Job, round.job_id).status = status
        session.add(ExecutionSession(task_id=task_id, session_id=str(uuid4()), status='ready'))
    target = tmp_path / str(task_id)
    target.mkdir()
    (target / 'session.json').write_text('original session')
    return task_id, UUID(receipt.roundId), target


def test_default_disabled_without_database_or_filesystem_access():
    assert cleanup_file(None, None, 'invalid').status == 'disabled'
    assert cleanup_session(None, 'invalid', 'invalid').status == 'disabled'
    assert cleanup_pending_object(None, None, 'invalid').status == 'disabled'
    with pytest.raises(ValueError):
        CleanupPolicy(file_cutoff=utcnow().replace(tzinfo=None))


def test_unsupported_database_is_retained(files_env, tmp_path):
    _, factory, store, _ = files_env
    assert cleanup_file(factory, store, uuid4(), POLICY).status == 'unsupported_database'
    assert cleanup_session(factory, tmp_path, uuid4(), POLICY).status == 'unsupported_database'


@pytest.mark.parametrize('status', ['staging', 'failed'])
def test_file_cleanup_removes_bytes_and_metadata(pg_tasks, status):
    factory, user, _, _ = pg_tasks
    file_id, key = orphan(factory, user, status)
    store = MemoryStore()
    store.objects[key] = b'content'
    assert cleanup_file(factory, store, file_id, POLICY).status == 'removed'
    assert key not in store.objects
    with factory() as session:
        assert session.get(FileRecord, file_id) is None
        assert session.scalars(select(CleanupObject)).all() == []


def test_storage_failure_has_durable_retry(pg_tasks):
    factory, user, _, _ = pg_tasks
    file_id, key = orphan(factory, user)
    store = MemoryStore()
    store.objects[key], store.fail_remove = b'content', True
    result = cleanup_file(factory, store, file_id, POLICY)
    assert result.status == 'storage_error'
    with factory() as session:
        assert session.get(FileRecord, file_id) is None
        receipt = session.get(CleanupObject, result.receipt_id)
        assert receipt.object_key == key
    store.fail_remove = False
    assert cleanup_pending_object(factory, store, result.receipt_id, POLICY).status == 'removed'
    assert key not in store.objects
    assert cleanup_pending_object(factory, store, result.receipt_id, POLICY).status == 'missing'


@pytest.mark.parametrize('kind', ['source', 'template', 'version', 'archive'])
def test_all_references_protect_even_deleted_parents(pg_tasks, tmp_path, kind):
    factory, user, _, _ = pg_tasks
    task_id, round_id, _ = task_setup(pg_tasks, tmp_path)
    file_id, key = orphan(factory, user)
    with factory.begin() as session:
        if kind == 'source':
            session.add(TaskSource(task_id=task_id, file_id=file_id, slot=19, name='source'))
        elif kind == 'template':
            template = TemplateRecord(owner_id=user.id, deleted_at=OLD)
            session.add(template)
            session.flush()
            version = TemplateVersionRecord(template_id=template.id, version=1, owner_id=user.id,
                operator_id=user.id, name='old', mode='wallpaper', notes='', enabled=False,
                skill_binding='module_default', skill_name='')
            session.add(version)
            session.flush()
            session.add(TemplateImageRecord(template_version_id=version.id, slot=0,
                name='old', file_id=file_id))
        else:
            slot = session.scalar(select(ResultSlotRecord).where(ResultSlotRecord.task_id == task_id))
            source = session.scalar(select(TaskSource).where(TaskSource.task_id == task_id))
            version = ImageVersion(slot_id=slot.id, round_id=round_id, version=1,
                file_id=file_id if kind == 'version' else source.file_id)
            session.add(version)
            session.flush()
            if kind == 'archive':
                archive = ArchiveRecord(task_id=task_id, owner_id=user.id, name='old', mode='text',
                    snapshot_hash='a'*64, deleted_at=OLD)
                session.add(archive)
                session.flush()
                session.add(ArchiveImage(archive_id=archive.id, slot=0,
                    image_version_id=version.id, file_id=file_id))
    store = MemoryStore()
    store.objects[key] = b'referenced'
    assert cleanup_file(factory, store, file_id, POLICY).status == 'referenced'
    assert store.objects[key] == b'referenced'


def test_ready_and_new_files_are_retained(pg_tasks):
    factory, user, _, _ = pg_tasks
    file_id, _ = orphan(factory, user, 'ready')
    assert cleanup_file(factory, MemoryStore(), file_id, POLICY).status == 'protected'
    file_id, _ = orphan(factory, user)
    with factory.begin() as session:
        session.get(FileRecord, file_id).updated_at = utcnow() + timedelta(hours=1)
    assert cleanup_file(factory, MemoryStore(), file_id, POLICY).status == 'protected'


def test_session_actual_removal_keeps_identity_audit(pg_tasks, tmp_path):
    factory, _, _, _ = pg_tasks
    task_id, _, target = task_setup(pg_tasks, tmp_path)
    assert cleanup_session(factory, tmp_path, task_id, POLICY).status == 'removed'
    assert not target.exists()
    with factory() as session:
        assert session.get(ExecutionSession, task_id).status == 'cleaned'
        assert session.get(TaskRecord, task_id) is not None
    assert cleanup_session(factory, tmp_path, task_id, POLICY).status == 'removed'


@pytest.mark.parametrize('status', ['queued', 'running', 'collecting', 'cancelling', 'uncertain'])
def test_active_round_retains_session(pg_tasks, tmp_path, status):
    task_id, _, target = task_setup(pg_tasks, tmp_path, status=status)
    assert cleanup_session(pg_tasks[0], tmp_path, task_id, POLICY).status == 'active_execution'
    assert (target / 'session.json').exists()


def test_reworkable_session_is_retained(pg_tasks, tmp_path):
    task_id, _, target = task_setup(pg_tasks, tmp_path, deleted=False, status='succeeded')
    assert cleanup_session(pg_tasks[0], tmp_path, task_id, POLICY).status == 'protected'
    assert target.exists()


@pytest.mark.parametrize('status', ['starting', 'running', 'uncertain'])
def test_unverified_attempt_retains_session(pg_tasks, tmp_path, status):
    factory, user, _, _ = pg_tasks
    task_id, round_id, target = task_setup(pg_tasks, tmp_path)
    with factory.begin() as session:
        session.add(ExecutionAttempt(round_id=round_id, task_id=task_id, operator_id=user.id,
            claim_token=uuid4(), node='test', workspace='untrusted', cli_version='test', status=status))
    assert cleanup_session(factory, tmp_path, task_id, POLICY).status == 'active_execution'
    assert target.exists()


def test_task_lock_excludes_cleanup(pg_tasks, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    factory, _, _, _ = pg_tasks
    task_id, _, target = task_setup(pg_tasks, tmp_path)
    with factory.begin() as session:
        session.scalar(select(TaskRecord).where(TaskRecord.id == task_id).with_for_update())
        with ThreadPoolExecutor() as pool:
            result = pool.submit(cleanup_session, factory, tmp_path, task_id, POLICY).result(timeout=5)
    assert result.status == 'busy'
    assert target.exists()


def test_reference_writer_excludes_file_cleanup(pg_tasks, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    factory, user, _, _ = pg_tasks
    task_id, _, _ = task_setup(pg_tasks, tmp_path)
    file_id, _ = orphan(factory, user)
    with factory.begin() as session:
        session.add(TaskSource(task_id=task_id, slot=18, file_id=file_id, name='pending'))
        session.flush()
        with ThreadPoolExecutor() as pool:
            result = pool.submit(cleanup_file, factory, MemoryStore(), file_id, POLICY).result(timeout=5)
    assert result.status == 'busy'
    assert cleanup_file(factory, MemoryStore(), file_id, POLICY).status == 'referenced'


def test_safe_path_rejects_escape_and_preserves_neighbor(tmp_path):
    with pytest.raises(ValueError):
        _safe_directory(tmp_path, '../outside')
    task_id, other_id = uuid4(), uuid4()
    target, other = tmp_path / str(task_id), tmp_path / str(other_id)
    target.mkdir()
    other.mkdir()
    assert _safe_directory(tmp_path, task_id) == target
    assert other.exists()


def test_archived_session_is_retained(pg_tasks, tmp_path):
    factory, user, _, _ = pg_tasks
    task_id, _, target = task_setup(pg_tasks, tmp_path)
    with factory.begin() as session:
        session.add(ArchiveRecord(task_id=task_id, owner_id=user.id, name='old', mode='text',
            snapshot_hash='b'*64, deleted_at=OLD))
    assert cleanup_session(factory, tmp_path, task_id, POLICY).status == 'referenced'
    assert target.exists()


def test_filesystem_failure_is_retryable(pg_tasks, tmp_path, monkeypatch):
    from app.worker import cleanup
    factory, _, _, _ = pg_tasks
    task_id, _, target = task_setup(pg_tasks, tmp_path)
    remove = cleanup.shutil.rmtree
    def fail(_):
        raise OSError('injected')
    monkeypatch.setattr(cleanup.shutil, 'rmtree', fail)
    assert cleanup_session(factory, tmp_path, task_id, POLICY).status == 'filesystem_error'
    assert target.exists()
    monkeypatch.setattr(cleanup.shutil, 'rmtree', remove)
    assert cleanup_session(factory, tmp_path, task_id, POLICY).status == 'removed'


def test_symlink_never_deletes_neighbor(pg_tasks, tmp_path):
    import os
    if os.name != 'posix':
        pytest.skip('POSIX symlink boundary runs on Linux')
    factory, _, _, _ = pg_tasks
    task_id, _, target = task_setup(pg_tasks, tmp_path)
    neighbor = tmp_path / 'neighbor'
    neighbor.mkdir()
    (neighbor / 'keep').write_text('protected')
    (target / 'linked').symlink_to(neighbor, target_is_directory=True)
    assert cleanup_session(factory, tmp_path, task_id, POLICY).status == 'unsafe_path'
    assert (neighbor / 'keep').read_text() == 'protected'


def test_file_row_lock_excludes_cleanup(pg_tasks):
    from concurrent.futures import ThreadPoolExecutor
    factory, user, _, _ = pg_tasks
    file_id, _ = orphan(factory, user)
    with factory.begin() as session:
        session.scalar(select(FileRecord).where(FileRecord.id == file_id).with_for_update())
        with ThreadPoolExecutor() as pool:
            result = pool.submit(cleanup_file, factory, MemoryStore(), file_id, POLICY).result(timeout=5)
    assert result.status == 'busy'
    with factory() as session:
        assert session.get(FileRecord, file_id) is not None
