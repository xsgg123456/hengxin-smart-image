"""Transaction-only integration hooks; callers own the final commit."""
from fastapi import HTTPException
from sqlalchemy import select
from . import service
from .models import DraftMaterial
from .schemas import DraftFields


def attach_uploaded(session, actor, material, draft_id):
    draft = service.owned(session, actor)
    if draft.epoch != draft_id:
        raise HTTPException(409, '草稿已清空或替换，请重新选择文件')
    if material.owner_id != actor.id or material.task_id or material.deleted_at or material.status != 'ready':
        raise HTTPException(409, '资料无法关联到当前草稿')
    link = session.scalar(select(DraftMaterial).where(DraftMaterial.material_id == material.id))
    if link:
        if link.draft_id != draft.id or link.epoch != draft.epoch:
            raise HTTPException(409, '资料已关联其他草稿')
        return
    service.check_capacity(session, draft)
    session.add(DraftMaterial(draft_id=draft.id, epoch=draft.epoch, material_id=material.id))
    session.flush()


def consume_for_task(session, actor, body, task, *, key=None):
    if body.draftId is None:
        return
    draft = service.owned(session, actor)
    if draft.epoch != body.draftId:
        raise HTTPException(409, '草稿已清空或提交，请刷新确认')
    service.check_version(draft, body.draftVersion)
    if any(row.state not in ('ready', 'cancelled') for row in service.imports(session, draft)):
        raise HTTPException(409, '附件尚未导入完成，请等待或处理失败附件')
    fields = {key: body.model_dump(mode='json')[key] for key in DraftFields.model_fields}
    if fields != draft.fields:
        raise HTTPException(409, '草稿内容尚未保存，请保存后再提交')
    if draft.source and (len(body.skus) != 1 or body.skus[0].code != draft.source['sku']):
        raise HTTPException(409, 'SKU与需求来源不一致，请重新获取需求或清空草稿')
    links = set(session.scalars(select(DraftMaterial.material_id).where(
        DraftMaterial.draft_id == draft.id, DraftMaterial.epoch == draft.epoch)))
    if links != set(body.materialIds or []):
        raise HTTPException(409, '草稿附件发生变化，请刷新后提交')
    submitted_key = key or draft.submit_key
    service.reset(session, draft)
    draft.last_submitted_task_id = task.id
    draft.last_submitted_key = submitted_key
    session.flush()
