from datetime import timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from app.db.timestamps import utcnow
from app.overseas.auth.models import Member
from app.overseas.permissions import authorize_member
from app.overseas.materials.models import Material
from app.overseas.materials.service import describe as describe_material
from .models import RequirementDraft, DraftImport, DraftMaterial
from .schemas import DraftFields, MAX_ATTACHMENTS


def owned(session, actor):
    # Serialize first creation and all user edits without a process-local mutex.
    member = session.scalar(select(Member).where(Member.id == actor.id).with_for_update()
                            .execution_options(populate_existing=True))
    if member is None:
        raise HTTPException(403, '海外账号无效')
    authorize_member(session, member, 'task.create')
    draft = session.scalar(select(RequirementDraft).where(RequirementDraft.owner_id == actor.id)
                           .with_for_update().execution_options(populate_existing=True))
    if draft is None:
        draft = RequirementDraft(owner_id=actor.id, fields=DraftFields().model_dump(mode='json'))
        session.add(draft)
        session.flush()
    return draft


def check_version(draft, version):
    if draft.version != version:
        raise HTTPException(409, '草稿已在其他页面修改，请先恢复最新草稿')


def touch(draft):
    draft.version += 1
    draft.updated_at = utcnow()


def materials(session, draft):
    return list(session.scalars(select(Material).join(DraftMaterial,
        DraftMaterial.material_id == Material.id).where(DraftMaterial.draft_id == draft.id,
        DraftMaterial.epoch == draft.epoch, Material.owner_id == draft.owner_id,
        Material.status == 'ready', Material.deleted_at.is_(None), Material.task_id.is_(None))
        .order_by(Material.created_at, Material.id)))


def imports(session, draft):
    return list(session.scalars(select(DraftImport).where(DraftImport.draft_id == draft.id,
        DraftImport.epoch == draft.epoch).order_by(DraftImport.created_at, DraftImport.id)))


def describe(session, draft):
    session.flush()
    from uuid import UUID
    from app.overseas.tasks.queries import eligible
    designer_id = draft.fields.get('designerId')
    designer = session.get(Member, UUID(designer_id)) if designer_id else None
    matched = ({'id': str(designer.id), 'name': designer.name, 'department': designer.department}
               if designer and designer.directory_state == 'enrolled' and eligible(session, designer) else None)
    return {'id': str(draft.epoch), 'version': draft.version, 'fields': draft.fields,
        'matchedDesigner': matched,
        'source': draft.source, 'submitKey': draft.submit_key,
        'updatedAt': draft.updated_at.replace(tzinfo=timezone.utc) if draft.updated_at.tzinfo is None else draft.updated_at,
        'lastSubmittedTaskId': str(draft.last_submitted_task_id) if draft.last_submitted_task_id else None,
        'lastSubmittedKey': draft.last_submitted_key,
        'materials': [describe_material(session, row) for row in materials(session, draft)],
        'imports': [{'id': str(row.id), 'sourceFileId': row.source_file_id,
            'filename': row.filename, 'size': row.size, 'kind': row.kind, 'state': row.state,
            'progress': row.progress, 'error': row.error,
            'materialId': str(row.material_id) if row.material_id else None} for row in imports(session, draft)]}


def finish(session, draft):
    result = describe(session, draft)
    session.commit()
    return result


def reset(session, draft):
    session.execute(update(DraftImport).where(DraftImport.draft_id == draft.id,
        DraftImport.epoch == draft.epoch).values(state='cancelled', lease_token=None, lease_until=None))
    session.execute(delete(DraftMaterial).where(DraftMaterial.draft_id == draft.id))
    draft.epoch, draft.submit_key = uuid4(), str(uuid4())
    draft.fields, draft.source = DraftFields().model_dump(mode='json'), None
    touch(draft)


def save(session, actor, body):
    draft = owned(session, actor)
    check_version(draft, body.version)
    draft.fields = body.fields.model_dump(mode='json')
    touch(draft)
    return finish(session, draft)


def clear(session, actor, body):
    draft = owned(session, actor)
    check_version(draft, body.version)
    reset(session, draft)
    return finish(session, draft)


def current_import(session, draft, identifier):
    row = session.scalar(select(DraftImport).where(DraftImport.id == identifier,
        DraftImport.draft_id == draft.id, DraftImport.epoch == draft.epoch).with_for_update()
        .execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(404, '草稿附件不存在')
    return row


def modify_import(session, actor, identifier, retry=False):
    draft = owned(session, actor)
    row = current_import(session, draft, identifier)
    if retry:
        if row.state != 'failed':
            return finish(session, draft)
        row.state, row.error, row.attempts = 'queued', None, 0
        row.progress, row.available_at = 0, utcnow()
    else:
        row.state, row.lease_token, row.lease_until = 'cancelled', None, None
        if row.material_id:
            session.execute(delete(DraftMaterial).where(DraftMaterial.draft_id == draft.id,
                DraftMaterial.material_id == row.material_id))
    touch(draft)
    return finish(session, draft)


def remove_material(session, actor, identifier):
    draft = owned(session, actor)
    link = session.scalar(select(DraftMaterial).where(DraftMaterial.draft_id == draft.id,
        DraftMaterial.epoch == draft.epoch, DraftMaterial.material_id == identifier))
    if link is None:
        raise HTTPException(404, '草稿资料不存在')
    session.delete(link)
    session.execute(update(DraftImport).where(DraftImport.draft_id == draft.id,
        DraftImport.epoch == draft.epoch, DraftImport.material_id == identifier)
        .values(state='cancelled', lease_token=None, lease_until=None))
    touch(draft)
    return finish(session, draft)


def check_capacity(session, draft, extra=1):
    jobs = imports(session, draft)
    pending = sum(row.state in ('queued', 'running', 'failed') for row in jobs)
    if len(materials(session, draft)) + pending + extra > MAX_ATTACHMENTS:
        raise HTTPException(422, f'每份图需最多 {MAX_ATTACHMENTS} 份附件，请先移除多余附件')
