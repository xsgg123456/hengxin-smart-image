import hashlib
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select

from app.core.config import get_settings
from app.models import utcnow
from .models import ApiFile, ApiItem, ApiTask, ApiVersion


def picture(record):
    return {'fileId': str(record.id), 'name': record.name,
            'url': f'/api/v1/api-image-edits/files/{record.id}/content'}


def find_file(session, file_id, lock=False):
    query = select(ApiFile).where(ApiFile.id == file_id)
    record = session.scalar(query.with_for_update() if lock else query)
    if not record or record.status != 'ready' or record.deleted_at:
        raise HTTPException(404, '图片不存在')
    return record


def new_record(owner_id, image):
    file_id = uuid4()
    return ApiFile(id=file_id, owner_id=owner_id, name=image.name,
                   bucket=get_settings().minio_bucket, object_key=f'api-image-edits/{file_id}',
                   content_type=image.content_type, checksum=image.checksum,
                   size_bytes=len(image.data), width=image.width, height=image.height,
                   status='staging')


def save_upload(session, store, user, image):
    record = new_record(user.id, image)
    session.add(record)
    session.commit()
    try:
        store.put(record, image.data)
    except Exception:
        record.status = 'failed'
        session.commit()
        raise HTTPException(503, '图片存储暂时不可用，请重试') from None
    record.status = 'ready'
    session.commit()
    return record


def delete_file(session, file_id, user):
    record = find_file(session, file_id, lock=True)
    item = session.scalar(select(ApiItem.id).where(or_(ApiItem.source_id == file_id,
                                                       ApiItem.result_id == file_id,
                                                       ApiItem.revision_source_id == file_id,
                                                       ApiItem.revision_annotation_id == file_id,
                                                       *(ApiItem.revision_snapshot['fileIds'][index].as_string() == str(file_id)
                                                         for index in range(4)))).limit(1))
    task = session.scalar(select(ApiTask.id).where(ApiTask.material_id == file_id).limit(1))
    version = session.scalar(select(ApiVersion.id).where(or_(ApiVersion.file_id == file_id,
                                                              ApiVersion.annotation_id == file_id)).limit(1))
    if item or task or version:
        raise HTTPException(409, '图片仍被任务引用')
    record.deleted_at, record.deleted_by = utcnow(), user.id
    session.commit()


def read_bytes(store, record):
    stream = store.open(record)
    try:
        chunks, total = [], 0
        for chunk in stream.stream(64 * 1024):
            total += len(chunk)
            if total > record.size_bytes:
                raise ValueError('stored image size mismatch')
            chunks.append(chunk)
        data = b''.join(chunks)
        if len(data) != record.size_bytes or hashlib.sha256(data).hexdigest() != record.checksum:
            raise ValueError('stored image incomplete')
        return data
    finally:
        try:
            stream.close()
        finally:
            stream.release_conn()
