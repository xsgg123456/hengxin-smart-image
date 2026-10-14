from hashlib import sha256
from uuid import uuid4
from fastapi import HTTPException
from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.modules.files.delivery import FileDelivery
from app.overseas.attachment_delivery import deliver
from app.overseas.tasks.service import lock_actor
from .models import Material
from . import parsers, service

from app.overseas.upload_limits import MAX_UPLOAD_BYTES

MAX_BYTES = MAX_UPLOAD_BYTES


def save_upload(session, store, actor, data, filename, kind):
    name, content_type = parsers.validate_document(data, filename, kind)
    actor = lock_actor(session, actor, 'task.create')
    identifier = uuid4()
    record = Material(id=identifier, owner_id=actor.id, kind=kind, name=name,
                      bucket=get_settings().minio_bucket, object_key=f'materials/{identifier}',
                      content_type=content_type, size_bytes=len(data), checksum=sha256(data).hexdigest(),
                      status='staging', version=0)
    session.add(record)
    session.commit()
    try:
        store.put(record, data)
    except Exception:
        record.status = 'failed'
        session.commit()
        raise HTTPException(503, '资料存储暂时不可用，请重新上传') from None
    # Revalidate after the staging commit before making the document visible.
    lock_actor(session, actor, 'task.create')
    record.status = 'ready'
    result = service.describe(session, record)
    try:
        session.commit()
    except Exception:
        session.rollback()
        # Commit may already have succeeded: keep the original object.
        raise HTTPException(503, '资料记录保存失败，请刷新后重试') from None
    return result


def delete(session, store, actor, material_id):
    actor = lock_actor(session, actor, 'task.create')
    record = service.find(session, material_id, lock=True, deleted=True)
    service.owned(session, record, actor)
    record.deleted_at = record.deleted_at or utcnow()
    delivery = FileDelivery.capture(record)
    # Tombstone commit happens before deleting storage; never delete after an unknown commit.
    session.commit()
    try:
        store.remove(delivery)
    except Exception:
        raise HTTPException(503, '资料已隐藏，原件清理失败，请再次删除重试') from None


def content(session, store, actor, material_id, *, head=False):
    record = FileDelivery.capture(service.readable(session, material_id, actor))
    session.close()
    return deliver(store, record, head=head)
