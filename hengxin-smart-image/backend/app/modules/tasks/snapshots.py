from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.modules.skills.service import resolve_binding
from app.modules.templates.service import find_template, read_current
from app.resource_models import FileRecord


def frozen_input(session, body):
    if not body.name.strip() or len(body.name.strip()) > 60:
        raise HTTPException(422, '任务名称须为1至60个字符')
    if body.sku is not None and len(body.sku.strip()) > 80:
        raise HTTPException(422, 'SKU不能超过80个字符')
    if not 1 <= len(body.sources) <= 20:
        raise HTTPException(422, '素材须包含1至20张图片')
    if len(body.note) > 1000:
        raise HTTPException(422, '修改要求不能超过1000个字符')
    sources = []
    for picture in body.sources:
        try:
            file_id = UUID(picture.fileId)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(422, '素材必须引用已上传文件') from None
        file = session.get(FileRecord, file_id)
        if not file or file.status != 'ready' or file.deleted_at:
            raise HTTPException(422, '素材不存在或尚未上传完成')
        sources.append(file)
    snapshot = None
    if body.mode == 'text':
        if not body.note.strip():
            raise HTTPException(422, '请输入自然语言修改要求')
        skill = resolve_binding(session, body.mode, body.skillVersionId)
    else:
        try:
            template_id = UUID(body.templateId)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(422, '请选择模板') from None
        record = find_template(session, template_id, lock=True)
        template = read_current(session, record)
        if body.templateVersion != template.version:
            raise HTTPException(409, '模板版本已变化，请刷新后重试')
        if template.mode != body.mode or not template.active:
            raise HTTPException(422, '模板类型不匹配或不可用')
        if not 1 <= len(template.images) <= 20:
            raise HTTPException(422, '模板须包含1至20张图片')
        for image in template.images:
            file = session.get(FileRecord, UUID(image.fileId))
            if not file or file.status != 'ready' or file.deleted_at:
                raise HTTPException(422, '模板图片不存在或尚未上传完成')
        skill = resolve_binding(session, body.mode, template.skillVersionId)
        if body.skillVersionId is not None and body.skillVersionId != template.skillVersionId:
            raise HTTPException(409, 'Skill与模板冻结版本不一致')
        snapshot = template.model_dump()
    if skill:
        from app.modules.skills.service import get_version
        skill = get_version(session, skill.id, lock=True)
    if not skill or skill.status != 'available':
        raise HTTPException(422, '没有可用的 Skill 版本')
    return sources, snapshot, skill
