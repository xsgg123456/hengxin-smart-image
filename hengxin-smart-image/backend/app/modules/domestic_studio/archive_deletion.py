"""Super-administrator deletion of independently copied archive files."""
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.overseas.tasks.cleanup_files import remove_object
from app.storage.minio_store import get_store
from .archive_models import Archive, ArchiveDeletion, ArchiveFile
from .archive_service import archive_key, verify_snapshot
from . import maintenance_lock
from .bindings import lock_admission
from .conversation_service import lock_actor
from .conversation_models import ConversationDeletion


def request(session, actor_id, identity):
    actor = lock_actor(session, actor_id)
    if actor.role != 'super_admin':
        raise HTTPException(403, '仅超级管理员可以删除成品')
    lock_admission(session)
    # A preparing archive may hold its own row while copying. Never wait for
    # that I/O while holding the global admission/permission locks.
    visible = session.get(Archive, identity)
    receipt = session.get(ArchiveDeletion, identity)
    if receipt and receipt.status == 'deleted':
        return {'archiveId': str(identity), 'status': 'deleted'}
    if visible is None or visible.status != 'ready':
        raise HTTPException(404, '成品不存在')
    source_deletion = session.get(ConversationDeletion, visible.source_conversation_id)
    if source_deletion and source_deletion.status != 'deleted':
        raise HTTPException(409, '源会话正在清理，请稍后删除成品')
    if receipt and receipt.status == 'deleting':
        return {'archiveId': str(identity), 'status': 'deleting'}
    record = session.scalar(select(Archive).where(Archive.id == identity).with_for_update())
    if record is None or record.status != 'ready':
        raise HTTPException(404, '成品不存在')
    if receipt is None:
        receipt = ArchiveDeletion(archive_id=identity, status='deleting')
        session.add(receipt)
    elif receipt.status == 'delete_failed':
        receipt.status, receipt.error = 'deleting', None
    elif receipt.status != 'deleting':
        raise HTTPException(409, '成品删除状态异常，请联系管理员')
    session.flush()
    return {'archiveId': str(identity), 'status': receipt.status}


def status(session, actor, identity):
    if actor.role != 'super_admin':
        raise HTTPException(403, '仅超级管理员可以查看删除状态')
    receipt = session.get(ArchiveDeletion, identity)
    if receipt is None:
        raise HTTPException(404, '成品删除记录不存在')
    return {'archiveId': str(identity), 'status': receipt.status, 'error': receipt.error}


def locked(session, identity):
    record = session.scalar(select(Archive).where(Archive.id == identity).with_for_update())
    receipt = session.scalar(select(ArchiveDeletion).where(ArchiveDeletion.archive_id == identity)
                             .with_for_update(skip_locked=True).execution_options(populate_existing=True))
    if record is None or receipt is None or receipt.status != 'deleting' or record.status != 'ready':
        return None, None
    return record, receipt


def process(factory, store, identity):
    try:
        with factory() as session:
            archive = session.get(Archive, identity)
            if archive is None:
                return False
            conversation_id = archive.source_conversation_id
        with maintenance_lock.hold(get_settings(), conversation_id):
            return _process(factory, store, identity)
    except (OSError, ValueError):
        return False


def _process(factory, store, identity):
    try:
        with factory.begin() as session:
            record, receipt = locked(session, identity)
            if receipt is None:
                return False
            rows = session.scalars(select(ArchiveFile).where(ArchiveFile.archive_id == identity)).all()
            verify_snapshot(record, rows)
            for row in rows:
                expected = archive_key(record, row.id)
                if row.object_key != expected or row.status != 'ready':
                    raise ValueError('Archive object ownership mismatch')
            for row in rows:
                remove_object(store, {'bucket': row.bucket, 'object_key': row.object_key})
            session.execute(delete(ArchiveFile).where(ArchiveFile.archive_id == identity))
            session.execute(delete(Archive).where(Archive.id == identity))
            receipt.status, receipt.error = 'deleted', None
        return True
    except Exception:
        with factory.begin() as session:
            _, receipt = locked(session, identity)
            if receipt:
                receipt.status, receipt.error = 'delete_failed', '成品清理未完成，请重试或联系管理员'
        return False


def cleanup_once(factory, store=None):
    with factory() as session:
        identities = session.scalars(select(ArchiveDeletion.archive_id).where(
            ArchiveDeletion.status == 'deleting').order_by(ArchiveDeletion.created_at).limit(5)).all()
    return sum(process(factory, store or get_store(), identity) for identity in identities)
