"""Archive immutable versions under the same task lock used by revisions and publishing."""
import hashlib

from fastapi import HTTPException
from sqlalchemy import func, select

from app.contracts import business as b
from app.modules.auth.permissions import authorize
from app.modules.files.deletions import logical_delete
from app.modules.files.service import find_file
from app.modules.tasks.models import ACTIVE, ImageVersion, ResultSlotRecord, RoundRecord, TaskRecord
from app.modules.tasks.queries import picture, stamp
from .models import ArchiveImage, ArchiveRecord, ArchiveRequest


def digest(ids):
    return hashlib.sha256(','.join(str(i) for i in ids).encode()).hexdigest()


def find_archive(session, archive_id, lock=False):
    statement = select(ArchiveRecord).where(ArchiveRecord.id == archive_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    archive = session.scalar(statement)
    if not archive or archive.deleted_at:
        raise HTTPException(404, '成品不存在或已删除')
    return archive


def serialize(session, archive):
    images = session.scalars(select(ArchiveImage).where(ArchiveImage.archive_id == archive.id)
                             .order_by(ArchiveImage.slot)).all()
    return b.Archive(id=str(archive.id), taskId=str(archive.task_id), name=archive.name,
        mode=archive.mode, ownerId=str(archive.owner_id), time=stamp(archive.created_at),
        imageVersionIds=[str(i.image_version_id) for i in images], images=[picture(
            find_file(session, i.file_id), session.get(ImageVersion, i.image_version_id).version)
            for i in images])


def create_archive(session, user, task_id, body, key=None):
    authorize(user)
    if key is not None and (not key.strip() or len(key) > 128):
        raise HTTPException(422, '归档请求键须为1至128字符')
    task = session.scalar(select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
                          .execution_options(populate_existing=True))
    if not task or task.deleted_at:
        raise HTTPException(404, '任务不存在')
    requested = body.imageVersionIds if body else None
    body_hash = digest(requested or [])
    if key:
        previous = session.scalar(select(ArchiveRequest).where(ArchiveRequest.task_id == task.id,
            ArchiveRequest.user_id == user.id, ArchiveRequest.key == key))
        if previous:
            if previous.body_hash != body_hash:
                raise HTTPException(409, '相同归档请求键不能提交不同版本')
            return serialize(session, find_archive(session, previous.archive_id))
    rounds = session.scalars(select(RoundRecord).where(RoundRecord.task_id == task.id)).all()
    current = next((r for r in rounds if r.id == task.current_round_id), None)
    slots = session.scalars(select(ResultSlotRecord).where(ResultSlotRecord.task_id == task.id)
                           .order_by(ResultSlotRecord.slot)).all()
    if (any(r.status in ACTIVE for r in rounds) or not current or current.status != 'succeeded'
            or not slots or any(not s.current_version_id or s.error for s in slots)):
        raise HTTPException(409, '整套图片全部完成且无执行中轮次后才能归档')
    version_ids = [s.current_version_id for s in slots]
    if requested is not None and requested != version_ids:
        raise HTTPException(409, '图片版本已变化，请刷新详情后重新归档')
    snapshot_hash = digest(version_ids)
    archive = session.scalar(select(ArchiveRecord).where(ArchiveRecord.task_id == task.id,
        ArchiveRecord.snapshot_hash == snapshot_hash, ArchiveRecord.deleted_at.is_(None)))
    if not archive:
        archive = ArchiveRecord(task_id=task.id, owner_id=user.id, name=task.name,
                                mode=task.mode, snapshot_hash=snapshot_hash)
        session.add(archive)
        session.flush()
        for slot in slots:
            version = session.get(ImageVersion, slot.current_version_id)
            if not version or version.slot_id != slot.id:
                raise HTTPException(409, '图片版本不完整，请刷新详情')
            find_file(session, version.file_id)
            session.add(ArchiveImage(archive_id=archive.id, slot=slot.slot,
                image_version_id=version.id, file_id=version.file_id))
    if key:
        session.add(ArchiveRequest(task_id=task.id, user_id=user.id, key=key,
                                  body_hash=body_hash, archive_id=archive.id))
    session.flush()
    result = serialize(session, archive)
    session.commit()
    return result


def list_archives(session, query):
    statement = select(ArchiveRecord).where(ArchiveRecord.deleted_at.is_(None))
    if query.mode:
        statement = statement.where(ArchiveRecord.mode == query.mode)
    if query.search:
        statement = statement.where(ArchiveRecord.name.icontains(query.search, autoescape=True))
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = session.scalars(statement.order_by(ArchiveRecord.created_at.desc(), ArchiveRecord.id)
        .offset((query.page - 1) * query.pageSize).limit(query.pageSize)).all()
    return b.PageResult[b.Archive](items=[serialize(session, a) for a in rows],
                                   page=query.page, pageSize=query.pageSize, total=total)


def delete_archive(session, user, archive_id):
    archive = find_archive(session, archive_id, lock=True)
    logical_delete(session, archive, 'archive', user)
    session.commit()
