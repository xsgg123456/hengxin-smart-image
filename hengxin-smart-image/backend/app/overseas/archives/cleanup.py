"""Verified object erasure under the same locks as archive publication."""
from hashlib import sha256
from pathlib import PurePosixPath
from uuid import UUID
from sqlalchemy import delete, select
from app.core.config import get_settings
from app.overseas.db import require_overseas_context
from app.storage.minio_store import get_store
from app.overseas.tasks.cleanup_files import remove_object
from app.overseas.tasks.models import ExecutionObject, TaskRequest
from app.overseas.materials.models import Material
from app.overseas.pictures.models import PictureVersion
from app.overseas.studio.models import Upload, Picture
from .models import Archive, ArchiveAsset, ArchiveEvent, ArchiveDeletion
from .deletion import locked

ERROR = '归档清理尚未完成，请重试或联系管理员'


def owned(key, identity):
    parts = PurePosixPath(key).parts
    if (len(parts) < 4 or parts[0] != 'archives' or parts[2] != str(identity)
            or '..' in parts or '\\' in key or ':' in key or key.startswith('/')):
        return False
    try:
        return str(UUID(parts[1])) == parts[1] and key == '/'.join(parts)
    except ValueError:
        return False


def inventory(session, store, record):
    rows = session.scalars(select(ArchiveAsset).where(ArchiveAsset.archive_id == record.id)).all()
    objects = {(row.bucket, row.object_key) for row in rows}
    buckets = {get_settings().minio_bucket, *(bucket for bucket, _ in objects)}
    # Historical source tasks can be gone. Discover this UUID's exact namespaces
    # including orphaned writes; nothing outside them is ever a deletion target.
    for bucket in buckets:
        for key in store.keys(bucket, 'archives/'):
            if not key.startswith('archives/'):
                raise ValueError('Storage listing escaped requested namespace')
            if owned(key, record.id):
                objects.add((bucket, key))
    for bucket, key in objects:
        if not owned(key, record.id):
            raise ValueError('Unsafe archive object namespace')
        if record.task_id and PurePosixPath(key).parts[1] != str(record.task_id):
            raise ValueError('Archive source namespace mismatch')
        for model in (Material, Upload, Picture, PictureVersion, ExecutionObject):
            if session.scalar(select(model.id).where(model.bucket == bucket,
                    model.object_key == key).limit(1)):
                raise ValueError('Archive shares source storage')
        if session.scalar(select(ArchiveAsset.id).where(ArchiveAsset.bucket == bucket,
                ArchiveAsset.object_key == key, ArchiveAsset.archive_id != record.id).limit(1)):
            raise ValueError('Archive shares another archive storage')
    return sorted(objects)


def erase_records(session, record, task):
    if task:
        identities = [UUID(value.split(':', 1)[1]) for value in record.versions if value.startswith('studio:')]
        for picture in session.scalars(select(Picture).where(Picture.task_id == task.id, Picture.id.in_(identities))):
            picture.sku = None
        if task.status in ('archived', 'completed'):
            task.status = 'studio' if task.workflow == 'studio' else 'generating'
        task.version += 1
        # Preserve old keys as conflicts, so they cannot replay a vanished archive
        # or silently create a new archive after later re-archiving.
        for request in session.scalars(select(TaskRequest).where(TaskRequest.task_id == task.id,
                TaskRequest.operation.in_(('archived', 'studio_archive', 'studio_complete')))):
            request.body_hash = sha256(('deleted:' + request.body_hash).encode()).hexdigest()
    for model in (ArchiveEvent, ArchiveAsset):
        session.execute(delete(model).where(model.archive_id == record.id))
    session.delete(record)


def process(factory, store, identity):
    try:
        with factory.begin() as session:
            task, record, row = locked(session, identity)
            if row is None or row.status != 'deleting':
                return False
            if record is None:
                raise ValueError('Archive missing before verified erasure')
            objects = inventory(session, store, record)
            for bucket, key in objects:
                remove_object(store, dict(bucket=bucket, object_key=key))
            # Re-list to catch failed removals and writes left by rolled-back SQL.
            remaining = inventory(session, store, record)
            # Asset references persist until the final transaction; verify absence individually.
            from types import SimpleNamespace
            from minio.error import S3Error
            for bucket, key in remaining:
                try:
                    store.stat(SimpleNamespace(bucket=bucket, object_key=key))
                except (KeyError, FileNotFoundError):
                    continue
                except S3Error as exc:
                    if exc.code in ('NoSuchKey', 'NoSuchObject'):
                        continue
                    raise
                raise OSError('Archive object remains')
            erase_records(session, record, task)
            row.status, row.error = 'deleted', None
        return True
    except Exception:
        with factory.begin() as session:
            _, _, row = locked(session, identity)
            if row and row.status != 'deleted':
                row.status, row.error = 'delete_failed', ERROR
        return False


def cleanup_once(factory, store=None):
    require_overseas_context()
    store = store or get_store()
    with factory() as session:
        identities = session.scalars(select(ArchiveDeletion.archive_id).where(
            ArchiveDeletion.status == 'deleting').order_by(ArchiveDeletion.created_at).limit(20)).all()
    return sum(process(factory, store, identity) for identity in identities)
