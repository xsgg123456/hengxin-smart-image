"""Durable idle-only erasure, executed by the owning native CLI maintenance user."""
from datetime import timedelta
import logging
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from fastapi import HTTPException
from minio.error import S3Error
from sqlalchemy import select
from app.core.config import get_settings
from app.execution.process import same_process
from app.models import utcnow
from . import deletion_files, deletion_paths, deletion_records
from .deletion_models import ApiTaskDeletion
from .deletion_state import reasons
from .models import ApiTask
from .state import channel


def dto(row):
    return {'state': {'delete_failed': 'failed'}.get(row.status, row.status), 'message': row.error}


def request(session, user, task_id):
    channel(session)
    task = session.scalar(select(ApiTask).where(ApiTask.id == task_id).with_for_update()
        .execution_options(populate_existing=True))
    row = session.get(ApiTaskDeletion, task_id, with_for_update=True)
    if row:
        if row.status == 'delete_failed':
            row.status, row.error, row.next_attempt_at = 'deleting', None, utcnow()
        response = dto(row)
        session.commit()
        return response
    if task is None or task.deleted_at:
        raise HTTPException(404, '任务不存在')
    reason = reasons(session, [task_id]).get(task_id)
    if reason:
        raise HTTPException(409, reason)
    row = ApiTaskDeletion(task_id=task_id, actor_id=user.id, status='deleting', phase='requested',
        manifest={}, next_attempt_at=utcnow())
    session.add(row)
    session.flush()
    response = dto(row)
    session.commit()
    return response


def status(session, task_id):
    row = session.get(ApiTaskDeletion, task_id)
    if row is None:
        raise HTTPException(404, '任务删除记录不存在')
    return dto(row)


def locked(session, task_id):
    channel(session)
    task = session.scalar(select(ApiTask).where(ApiTask.id == task_id).with_for_update()
        .execution_options(populate_existing=True))
    row = session.get(ApiTaskDeletion, task_id, with_for_update=True)
    return task, row


def stopped(session, task, settings):
    if reasons(session, [task.id]):
        raise RuntimeError('Execution has not ended')
    _, _, turns, _ = deletion_files.related(session, task)
    for turn in turns:
        identity = turn.process_identity
        if not identity:
            if turn.snapshot.get('executionDispatched'):
                raise RuntimeError('Process identity missing')
            continue  # Preflight failure or cancelled before dispatch has no process.
        if identity.get('node') != settings.worker_node_name:
            raise RuntimeError('Cleanup requires the original execution node')
        if same_process(identity['pid'], identity['boot'], identity['birth']):
            raise RuntimeError('Original process still exists')


def remove_object(store, bucket, key):
    row = SimpleNamespace(bucket=bucket, object_key=key)
    store.remove(row)
    try:
        store.stat(row)
    except S3Error as exc:
        if exc.code not in ('NoSuchKey', 'NoSuchObject'):
            raise
    except (KeyError, FileNotFoundError):
        return
    else:
        raise OSError('Object remains after deletion')


def process(factory, store, task_id, settings=None, now=None):
    settings, now = settings or get_settings(), now or utcnow()
    task_id = UUID(str(task_id))
    try:
        with factory.begin() as session:
            task, row = locked(session, task_id)
            if row is None or row.status == 'deleted':
                return 'missing' if row is None else 'deleted'
            if task is None:
                raise RuntimeError('Business task missing before completed deletion')
            stopped(session, task, settings)
            if row.phase == 'requested':
                row.manifest = {**deletion_files.freeze(session, task),
                    'root': str(Path(settings.codex_execution_root).absolute()),
                    'node': settings.worker_node_name}
                row.phase = 'prepared'
            if (row.manifest.get('root') != str(Path(settings.codex_execution_root).absolute())
                    or row.manifest.get('node') != settings.worker_node_name):
                raise RuntimeError('Deletion requires the original execution root and node')
            row.status, row.error = 'deleting', None
        # A committed task + file fence survives filesystem or object-store failure.
        with factory.begin() as session:
            task, row = locked(session, task_id)
            if row.status == 'deleted':
                return 'deleted'
            stopped(session, task, settings)
            for value in row.manifest['files']:
                from .models import ApiFile
                record = session.get(ApiFile, UUID(value), with_for_update=True)
                if record is None or deletion_files.shared(session, task_id, record):
                    raise RuntimeError('Frozen file ownership changed')
            objects = deletion_files.objects(session, row.manifest, store)
            for identifier in row.manifest['conversations']:
                deletion_paths.clean(settings.codex_execution_root, identifier)
            for bucket, key in objects:
                remove_object(store, bucket, key)
            deletion_records.erase(session, task, row.manifest, objects)
            row.status, row.phase, row.manifest = 'deleted', 'completed', {}
            row.error, row.next_attempt_at, row.completed_at = None, None, now
        return 'deleted'
    except Exception as error:
        logging.exception('API task deletion deferred: %s (%s)', task_id, type(error).__name__)
        with factory.begin() as session:
            _, row = locked(session, task_id)
            if row is not None and row.status != 'deleted':
                row.status, row.error = 'delete_failed', '删除未完成，资料仍处于删除保护中，可重试'
                row.attempts += 1
                row.next_attempt_at = now + timedelta(seconds=min(3600, 5 * 2 ** min(row.attempts, 9)))
        return 'delete_failed'


def run_pending(factory, store, settings=None, now=None, limit=10):
    settings, now = settings or get_settings(), now or utcnow()
    with factory() as session:
        ids = session.scalars(select(ApiTaskDeletion.task_id).where(
            ApiTaskDeletion.status.in_(('deleting', 'delete_failed')),
            ApiTaskDeletion.next_attempt_at <= now).order_by(ApiTaskDeletion.next_attempt_at).limit(limit)).all()
    return [{'taskId': str(identifier), 'status': process(factory, store, identifier, settings, now)} for identifier in ids]
