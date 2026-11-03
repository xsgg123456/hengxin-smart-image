from fastapi import HTTPException
from app.db.timestamps import utcnow
from . import source, service
from .models import DraftImport
from .schemas import MAX_ATTACHMENTS


def select_source(session, actor, body):
    # Permission is checked before outbound IO, then rechecked after it.
    draft = service.owned(session, actor)
    service.check_version(draft, body.version)
    actor_id = actor.id
    session.commit()
    data = source.fetch(body.sku)
    item = source.selected(data, body.requirementId)
    attachments = {}
    for file in item.get('files', []):
        metadata = source.attachment_metadata(file)
        attachments.setdefault(metadata['source_file_id'], metadata)
    if len(attachments) > MAX_ATTACHMENTS:
        raise HTTPException(422, f'来源附件超过 {MAX_ATTACHMENTS} 份，请在来源系统整理后重试')
    if len(body.fields.skus) != 1 or body.fields.skus[0].code != body.sku:
        raise HTTPException(422, '草稿SKU与所选来源不一致，请重新获取需求')
    from app.overseas.auth.models import Member
    draft = service.owned(session, session.get(Member, actor_id))
    service.check_version(draft, body.version)
    chosen = {'sku': body.sku, 'requirementId': body.requirementId}
    if draft.source != chosen:
        service.reset(session, draft)
    else:
        service.touch(draft)
    draft.source, draft.fields = chosen, body.fields.model_dump(mode='json')
    existing = {row.source_file_id for row in service.imports(session, draft)}
    fresh = [metadata for key, metadata in attachments.items() if key not in existing]
    service.check_capacity(session, draft, len(fresh))
    for metadata in fresh:
        session.add(DraftImport(draft_id=draft.id, epoch=draft.epoch, owner_id=actor_id,
            sku=body.sku, requirement_id=body.requirementId, available_at=utcnow(), **metadata))
    return service.finish(session, draft)
