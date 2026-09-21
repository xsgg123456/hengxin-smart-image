"""Freeze explicit single-image inputs under the task admission lock."""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.modules.management.settings import values
from app.resource_models import FileRecord
from .models import ImageVersion, ResultSlotRecord


def image_file(session, file_id):
    file = session.scalar(select(FileRecord).where(FileRecord.id == file_id).with_for_update())
    if (not file or file.status != 'ready' or file.deleted_at
            or file.content_type not in ('image/jpeg', 'image/png', 'image/webp')):
        raise HTTPException(422, '返工图片不存在或不可用')
    return file


def freeze_revision(session, user, task, body, current):
    fields = body.model_fields_set
    if body.target is None and (body.baseVersionId is not None or body.annotationFileId is not None):
        raise HTTPException(422, '整套修改不能指定单张基础版本或圈注截图')
    if body.retry:
        for field, original in [('baseVersionId', current.base_version_id),
                                ('annotationFileId', current.annotation_file_id)]:
            if field in fields and getattr(body, field) != (str(original) if original else None):
                raise HTTPException(409, '重试必须沿用原轮次的基础版本和圈注截图')
        # Do not reinterpret nullable legacy inputs as a request for the latest version.
        return (current.base_version_id, current.annotation_file_id,
                bool(current.execution_config.get('singleInputFrozen')))
    if body.target is None:
        return None, None, False
    slot = session.scalar(select(ResultSlotRecord).where(
        ResultSlotRecord.task_id == task.id, ResultSlotRecord.slot == body.target))
    base_id = UUID(body.baseVersionId) if body.baseVersionId else None
    if 'baseVersionId' not in fields:
        base_id = slot.current_version_id
    if base_id:
        version = session.get(ImageVersion, base_id)
        if not version or version.slot_id != slot.id:
            raise HTTPException(422, '基础版本不属于当前任务的目标图片')
        image_file(session, version.file_id)
    elif slot.current_version_id:
        raise HTTPException(422, '已有结果时必须指定所见基础版本')
    annotation_id = UUID(body.annotationFileId) if body.annotationFileId else None
    if annotation_id:
        file = image_file(session, annotation_id)
        if file.owner_id != user.id:
            raise HTTPException(403, '只能提交自己上传的圈注截图')
        if not 0 < file.size_bytes <= min(10 * 1024**2, values(session)['maxUploadBytes']):
            raise HTTPException(422, '圈注截图超过当前上传大小限制')
    return base_id, annotation_id, True
