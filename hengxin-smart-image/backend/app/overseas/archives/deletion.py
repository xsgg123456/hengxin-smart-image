"""Durable archive deletion requests and content-based confirmation snapshots."""
from hashlib import sha256
import json
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from app.overseas.permissions import authorize_member
from app.overseas.tasks.models import Task
from app.overseas.tasks.service import lock_actor
from .models import Archive, ArchiveAsset, ArchiveEvent, ArchiveDeletion


class DeleteArchive(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    deleteToken: str = Field(pattern=r'^[0-9a-f]{64}$')


def token(session, record):
    def values(row):
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}
    data = [values(record)]
    for model in (ArchiveAsset, ArchiveEvent):
        data.append([values(row) for row in session.scalars(select(model).where(
            model.archive_id == record.id).order_by(model.id))])
    return sha256(json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def locked(session, identity):
    # Always acquire the surviving source task before its archive. Re-read after waiting.
    source = session.scalar(select(Archive.task_id).where(Archive.id == identity))
    task = session.scalar(select(Task).where(Task.id == source).with_for_update()
        .execution_options(populate_existing=True)) if source else None
    record = session.scalar(select(Archive).where(Archive.id == identity).with_for_update()
        .execution_options(populate_existing=True))
    row = session.scalar(select(ArchiveDeletion).where(ArchiveDeletion.archive_id == identity)
        .with_for_update().execution_options(populate_existing=True))
    return task, record, row


def available(session, identity):
    if identity is not None and session.get(ArchiveDeletion, identity):
        raise HTTPException(409, '归档正在删除或删除失败，请完成删除后重新归档')


def dto(row):
    return dict(archiveId=str(row.archive_id), status=row.status, error=row.error)


def fields(session, record):
    row = session.get(ArchiveDeletion, record.id)
    return dict(deleteToken=token(session, record), deletionStatus=row.status if row else None,
                deletionError=row.error if row else None)


def request(session, actor, identity, body):
    lock_actor(session, actor, 'task.delete')
    _, record, row = locked(session, identity)
    if row is None:
        if record is None:
            raise HTTPException(404, '归档不存在')
        if token(session, record) != body.deleteToken:
            raise HTTPException(409, '归档内容已修改，请刷新后重新确认删除')
        row = ArchiveDeletion(archive_id=identity, status='deleting')
        session.add(row)
    elif row.status == 'delete_failed':
        row.status, row.error = 'deleting', None
    session.flush()
    result = dto(row)
    session.commit()
    return result


def status(session, actor, identity):
    authorize_member(session, actor, 'task.delete')
    row = session.get(ArchiveDeletion, identity)
    if row is None:
        raise HTTPException(404, '归档删除记录不存在')
    return dto(row)


def preview(session, actor, identity):
    """Confirm metadata even when an archived image is missing or corrupt."""
    from .service import dto as archive_dto
    from .snapshot import metadata
    authorize_member(session, actor, 'task.delete')
    task, record, _ = locked(session, identity)
    if record is None:
        raise HTTPException(404, '归档不存在')
    if record.created_by is None and task:
        metadata(session, record, task)
        session.flush()
    result = {**archive_dto(record), **fields(session, record)}
    session.commit()
    return result
