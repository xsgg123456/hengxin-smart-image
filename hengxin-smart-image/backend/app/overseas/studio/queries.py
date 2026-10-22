from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.tasks.queries import get_task
from app.overseas.tasks.models import TaskEvent
from app.overseas.archives.models import Archive, ArchiveAsset, ArchiveDeletion
from app.overseas.permissions import principal_for, require_task_access
from app.overseas.materials.models import Material
from app.overseas.management.skills import enabled_listing
from app.overseas.execution.models import Job, TERMINAL, ExecutionEvent
from .models import Turn, Upload, Picture, Conversation, Transcript
from .material_list import visible

ROOT = '/api/overseas/v1'


def access(session, actor, task_id, write=False):
    task = get_task(session, task_id, lock=write)
    require_task_access(principal_for(session, actor), task.created_by, task.designer_id,
                        'task.design' if write else 'task.read')
    if task.workflow != 'studio':
        raise HTTPException(409, '历史任务请使用原流程')
    return task


def asset(row, source):
    url = (f'{ROOT}/materials/{row.id}/content' if source == 'task' else
           f'{ROOT}/tasks/{row.task_id}/studio/files/{row.id}/content')
    return dict(id=f'{source if source == "task" else "upload"}:{row.id}', name=row.name,
                contentType=row.content_type, sizeBytes=row.size_bytes, url=url, source=source)


def attachment(session, task, identity):
    try:
        source, value = identity.split(':', 1)
        model = {'task': Material, 'upload': Upload}[source]
        row = session.get(model, UUID(value))
    except (ValueError, KeyError, AttributeError):
        raise HTTPException(422, '附件编号无效') from None
    if not row or row.task_id != task.id:
        raise HTTPException(404, '附件不存在或不属于当前任务')
    if source == 'task' and (row.deleted_at or row.status != 'ready'):
        raise HTTPException(409, '任务素材不可用')
    return row, source


def picture(session, task, identity):
    row = session.get(Picture, identity)
    if not row or row.task_id != task.id:
        raise HTTPException(404, '图片不存在或不属于当前任务')
    return row


def picture_dto(row):
    return dict(id=str(row.id), name=row.name,
                url=f'{ROOT}/tasks/{row.task_id}/studio/pictures/{row.id}/content',
                width=row.width, height=row.height, turnId=str(row.turn_id),
                sku=row.sku, archived=row.sku is not None, sourcePath=row.source_path)


def current_conversation(session, task_id):
    return session.scalar(select(Conversation).where(Conversation.task_id == task_id)
        .order_by(Conversation.created_at.desc(), Conversation.id.desc()).limit(1))


def available_archive(session, task_id, lock=False):
    query = select(Archive).where(Archive.task_id == task_id)
    record = session.scalar(query.with_for_update() if lock else query)
    if record is None or not record.versions or session.get(ArchiveDeletion, record.id):
        return None
    asset_id = session.scalar(select(ArchiveAsset.id).where(
        ArchiveAsset.archive_id == record.id,
        ArchiveAsset.source_version.in_(record.versions),
        ArchiveAsset.size_bytes > 0).limit(1))
    return record if asset_id else None


def view(session, actor, task_id):
    task = access(session, actor, task_id)
    turns = []
    active = None
    for turn in session.scalars(select(Turn).where(Turn.task_id == task.id).order_by(Turn.created_at, Turn.id)):
        job = session.get(Job, turn.job_id)
        if job.status not in TERMINAL:
            active = str(turn.id)
        attachments = [asset(*attachment(session, task, identity)) for identity in turn.attachment_ids]
        turns.append(dict(id=str(turn.id), conversationId=str(turn.conversation_id),
            text=turn.text, skillName=turn.skill_name, deliveryError=turn.delivery_error,
            status=job.status, reply=turn.reply, error=job.error, jobId=str(job.id),
            jobVersion=job.version, attachments=attachments,
            referencePictures=[picture_dto(picture(session, task, UUID(value)))
                               for value in turn.reference_ids],
            pictures=[picture_dto(p) for p in session.scalars(select(Picture).where(
                Picture.turn_id == turn.id).order_by(Picture.created_at, Picture.id))],
            createdAt=turn.created_at))
    channel = current_conversation(session, task.id)
    record = available_archive(session, task.id)
    reopened = session.scalar(select(TaskEvent.id).where(TaskEvent.task_id == task.id,
        TaskEvent.kind == 'task.studio_reopened').limit(1)) is not None
    return dict(taskId=str(task.id), conversationId=str(channel.id) if channel else None,
        completed=task.status == 'completed', taskVersion=task.version,
        archiveId=str(record.id) if record else None, reopened=reopened, turns=turns,
        materials=[asset(row, source) for row, source in visible(session, task.id)],
        skills=enabled_listing(session),
        activeTurnId=active)


def transcript(session, actor, task_id, after):
    access(session, actor, task_id)
    rows = list(session.scalars(select(Transcript).where(Transcript.task_id == task_id,
        Transcript.id > after).order_by(Transcript.id).limit(501)))
    more, rows = len(rows) > 500, rows[:500]
    return dict(items=[dict(id=row.id, turnId=str(row.turn_id), itemId=row.item_id,
        kind=row.kind, text=row.text, state=row.state, createdAt=row.created_at) for row in rows],
        cursor=rows[-1].id if rows else after, hasMore=more)


def events(session, actor, task_id, after):
    access(session, actor, task_id)
    rows = session.execute(select(ExecutionEvent, Turn.id).join(Turn,
        Turn.job_id == ExecutionEvent.job_id).where(ExecutionEvent.task_id == task_id,
        ExecutionEvent.id > after).order_by(ExecutionEvent.id).limit(500)).all()
    return dict(items=[dict(id=e.id, turnId=str(t), kind='status', text=e.message,
        createdAt=e.created_at) for e, t in rows], cursor=rows[-1][0].id if rows else after)
