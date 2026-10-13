"""Immutable, independently owned archive bytes; also protects pre-migration archives."""
from uuid import UUID, uuid5
from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.tasks.models import Task, TaskSku
from app.overseas.pictures.models import Picture, PictureVersion
from app.overseas.studio.models import Picture as StudioPicture
from app.overseas.studio.files import read
from .models import ArchiveAsset


def metadata(session, record, task):
    # Initialize once; task reassignment transfers designer access in its transaction.
    if record.created_by is None:
        record.product_name, record.brand, record.platform = task.product_name, task.brand, task.platform
        record.created_by, record.designer_id = task.created_by, task.designer_id
        record.skus = [{'code': code} for code in session.scalars(select(TaskSku.code)
            .where(TaskSku.task_id == task.id).order_by(TaskSku.position))]
        record.sku_search = '\n'.join(item['code'] for item in record.skus)


def assets(session, record):
    return session.scalars(select(ArchiveAsset).where(ArchiveAsset.archive_id == record.id)
        .order_by(ArchiveAsset.position, ArchiveAsset.id)).all()


def protect(session, store, record, task=None):
    """Called under the parent task lock, before any destructive side effect."""
    task = task or (session.get(Task, record.task_id) if record.task_id else None)
    if task:
        metadata(session, record, task)
    if record.created_by is None or record.designer_id is None or not record.skus:
        raise HTTPException(503, '归档权限或SKU信息不完整，已保留原任务')
    session.flush()
    existing = {row.source_version: row for row in assets(session, record)}
    if len(set(record.versions)) != len(record.versions):
        raise HTTPException(503, '归档版本清单异常，已保留原任务')
    for position, identity in enumerate(record.versions):
        row = existing.get(identity)
        if row is not None:
            read(store, row)
            continue
        if task is None:
            raise HTTPException(503, '归档文件不完整')
        if identity.startswith('studio:'):
            source = session.get(StudioPicture, UUID(identity.split(':', 1)[1]))
            owner = source
        else:
            source = session.get(PictureVersion, UUID(identity))
            owner = session.get(Picture, source.picture_id) if source else None
        if not owner or owner.task_id != task.id or not owner.sku:
            raise HTTPException(503, '归档版本关联异常，已保留原任务')
        if owner.sku not in {item['code'] for item in record.skus}:
            raise HTTPException(503, '归档SKU关联异常，已保留原任务')
        identity_id = uuid5(record.id, identity)
        row = ArchiveAsset(id=identity_id, archive_id=record.id, source_version=identity,
            position=position, sku=owner.sku, bucket=source.bucket,
            object_key=f'archives/{task.id}/{record.id}/{identity_id}', **{key: getattr(source, key)
                for key in ('name', 'content_type', 'size_bytes', 'checksum', 'width', 'height')})
        data = read(store, source)
        store.put(row, data)
        read(store, row)
        session.add(row)
    session.flush()
    if len(assets(session, record)) != len(record.versions):
        raise HTTPException(503, '归档数量校验失败，已保留原任务')
