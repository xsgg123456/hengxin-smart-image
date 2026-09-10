"""Explicit, disabled-by-default collection; never registered with the scheduler."""
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.models import Job
from app.modules.archives.models import ArchiveImage, ArchiveRecord
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession
from app.modules.tasks.models import ImageVersion, RoundRecord, TaskRecord, TaskSource
from app.modules.templates.models import TemplateImageRecord
from app.resource_models import FileRecord
from app.worker.leases import TERMINAL
from app.worker.cleanup_models import CleanupObject


@dataclass(frozen=True)
class CleanupPolicy:
    file_cutoff: datetime | None = None
    session_cutoff: datetime | None = None

    def __post_init__(self):
        for cutoff in (self.file_cutoff, self.session_cutoff):
            if cutoff is not None and (cutoff.tzinfo is None or cutoff.utcoffset() is None):
                raise ValueError('Cleanup cutoff must include a timezone')


@dataclass(frozen=True)
class CleanupResult:
    status: str
    # Storage failures retain an independent durable receipt for explicit retry.
    bucket: str | None = None
    object_key: str | None = None
    receipt_id: UUID | None = None


def _older(value, cutoff):
    if value is None:
        return False
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)) < cutoff


def _lock_tables(session, models):
    """NOWAIT avoids a table/row lock inversion with normal business writers."""
    connection = session.connection()
    quote = connection.dialect.identifier_preparer.quote
    mapping = connection.get_execution_options().get('schema_translate_map') or {}
    names = []
    for model in models:
        table = model.__table__
        schema = mapping.get(table.schema, table.schema)
        names.append((quote(schema) + '.' if schema else '') + quote(table.name))
    session.execute(text('LOCK TABLE ' + ', '.join(sorted(set(names)))
                         + ' IN SHARE ROW EXCLUSIVE MODE NOWAIT'))


def _busy(error):
    return getattr(error.orig, 'sqlstate', None) == '55P03'


def cleanup_file(factory, store, file_id, policy=CleanupPolicy()):
    if policy.file_cutoff is None:
        return CleanupResult('disabled')
    references = (TemplateImageRecord, TaskSource, ImageVersion, ArchiveImage)
    try:
        with factory.begin() as session:
            if session.get_bind().dialect.name != 'postgresql':
                return CleanupResult('unsupported_database')
            _lock_tables(session, (*references, FileRecord))
            record = session.scalar(select(FileRecord).where(FileRecord.id == UUID(str(file_id)))
                                    .with_for_update(nowait=True))
            if record is None:
                return CleanupResult('missing')
            if record.status not in ('staging', 'failed') or not _older(record.updated_at, policy.file_cutoff):
                return CleanupResult('protected')
            if any(session.scalar(select(model.id).where(model.file_id == record.id).limit(1))
                   for model in references):
                return CleanupResult('referenced')
            receipt = CleanupObject(bucket=record.bucket, object_key=record.object_key)
            session.add(receipt)
            session.delete(record)
            session.flush()
            receipt_id = receipt.id
        # Commit first: late writers must fail their FK/update instead of reviving removed bytes.
        return cleanup_pending_object(factory, store, receipt_id, policy)
    except OperationalError as error:
        if _busy(error):
            return CleanupResult('busy')
        raise


def cleanup_pending_object(factory, store, receipt_id, policy=CleanupPolicy()):
    if policy.file_cutoff is None:
        return CleanupResult('disabled')
    try:
        with factory.begin() as session:
            if session.get_bind().dialect.name != 'postgresql':
                return CleanupResult('unsupported_database')
            receipt = session.scalar(select(CleanupObject).where(CleanupObject.id == receipt_id)
                                     .with_for_update(nowait=True))
            if receipt is None:
                return CleanupResult('missing')
            result = CleanupResult('removed', receipt.bucket, receipt.object_key, receipt.id)
            try:
                store.remove(receipt)
            except Exception:
                return CleanupResult('storage_error', receipt.bucket, receipt.object_key, receipt.id)
            session.delete(receipt)
            return result
    except OperationalError as error:
        if _busy(error):
            return CleanupResult('busy')
        raise


def _safe_directory(root, task_id):
    root = Path(root).absolute()
    if root.is_symlink() or root.is_junction() or root.resolve() != root:
        raise ValueError('Execution root must not contain directory links')
    target = root / str(UUID(str(task_id)))
    if target.is_symlink() or target.is_junction() or target.resolve().parent != root:
        raise ValueError('Unsafe task directory')
    if target.exists() and not target.is_dir():
        raise ValueError('Task path must be a directory')
    # Refuse nested links as well, even though rmtree normally unlinks symlinks.
    for entry in target.rglob('*'):
        if entry.is_symlink() or entry.is_junction() or not entry.resolve().is_relative_to(target):
            raise ValueError('Linked task material must be inspected manually')
    return target


def cleanup_session(factory, root, task_id, policy=CleanupPolicy()):
    if policy.session_cutoff is None:
        return CleanupResult('disabled')
    try:
        with factory.begin() as session:
            if session.get_bind().dialect.name != 'postgresql':
                return CleanupResult('unsupported_database')
            _lock_tables(session, (RoundRecord, Job, ExecutionAttempt, ExecutionSession, ArchiveRecord))
            task = session.scalar(select(TaskRecord).where(TaskRecord.id == UUID(str(task_id)))
                                  .with_for_update(nowait=True))
            if task is None:
                return CleanupResult('missing')
            if not _older(task.deleted_at, policy.session_cutoff):
                return CleanupResult('protected')
            rounds = session.scalars(select(RoundRecord).where(RoundRecord.task_id == task.id)).all()
            for round in rounds:
                job = session.get(Job, round.job_id)
                if round.status not in TERMINAL or not job or job.status not in TERMINAL:
                    return CleanupResult('active_execution')
            attempts = session.scalars(select(ExecutionAttempt).where(ExecutionAttempt.task_id == task.id)).all()
            if any(a.status != 'finished' or a.finished_at is None for a in attempts):
                return CleanupResult('active_execution')
            identity = session.get(ExecutionSession, task.id)
            if identity and identity.status not in ('ready', 'cleaned'):
                return CleanupResult('active_execution')
            if session.scalar(select(ArchiveRecord.id).where(ArchiveRecord.task_id == task.id).limit(1)):
                return CleanupResult('referenced')
            try:
                target = _safe_directory(root, task.id)
                if target.exists():
                    shutil.rmtree(target)
            except ValueError:
                return CleanupResult('unsafe_path')
            except OSError:
                return CleanupResult('filesystem_error')
            if identity:
                identity.status = 'cleaned'
            return CleanupResult('removed')
    except OperationalError as error:
        if _busy(error):
            return CleanupResult('busy')
        raise
