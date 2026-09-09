import logging
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import get_settings
from app.resource_models import FileRecord

logger = logging.getLogger(__name__)


def save_upload(session, store, user, image):
    file_id = uuid4()
    record = FileRecord(
        id=file_id, owner_id=user.id, name=image.name, bucket=get_settings().minio_bucket,
        object_key=f'originals/{file_id}', content_type=image.content_type,
        checksum=image.checksum, size_bytes=len(image.data), width=image.width,
        height=image.height, status='staging',
    )
    session.add(record)
    # Durable staging precedes object writes: a crash leaves a trace, never a usable ghost.
    session.commit()
    try:
        store.put(record, image.data)
    except Exception:
        try:
            store.remove(record)
        except Exception:
            logger.warning('Staged object cleanup deferred: %s', file_id)
        record.status = 'failed'
        session.commit()
        raise HTTPException(503, '图片存储暂时不可用，请重试') from None
    record.status = 'ready'
    try:
        session.commit()
    except Exception:
        # An ambiguous commit may already have succeeded; never remove its object.
        # Otherwise the durable staging row remains inaccessible and can be reconciled.
        session.rollback()
        raise HTTPException(503, '图片记录保存失败，请重试') from None
    return record


def find_file(session, file_id):
    record = session.get(FileRecord, file_id)
    if not record or record.status != 'ready' or record.deleted_at is not None:
        raise HTTPException(404, '图片不存在')
    return record
