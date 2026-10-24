from uuid import UUID
from datetime import timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.tasks.queries import get_task
from app.overseas.tasks.models import TaskEvent
from app.overseas.archives.models import Archive, ArchiveAsset, ArchiveDeletion
from app.overseas.permissions import principal_for, require_task_access
from app.overseas.materials.models import Material
from app.overseas.management.skills import enabled_listing
from app.overseas.execution.models import Job, TERMINAL, ExecutionEvent
from .models import Turn, Upload, Picture, Conversation, Transcript, ConversationDeletion
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


def attachment(session, task, identity, conversation_id=None):
    try:
        source, value = identity.split(':', 1)
        model = {'task': Material, 'upload': Upload}[source]
        row = session.get(model, UUID(value))
    except (ValueError, KeyError, AttributeError):
        raise HTTPException(422, '附件编号无效') from None
    if not row or row.task_id != task.id:
        raise HTTPException(404, '附件不存在或不属于当前任务')
    if source == 'upload' and conversation_id is not None and row.conversation_id not in (None, conversation_id):
        raise HTTPException(404, '附件不属于当前会话')
    if source == 'task' and (row.deleted_at or row.status != 'ready'):
        raise HTTPException(409, '任务素材不可用')
    return row, source


def picture(session, task, identity, conversation_id=None):
    row = session.get(Picture, identity)
    if not row or row.task_id != task.id:
        raise HTTPException(404, '图片不存在或不属于当前任务')
    if conversation_id is not None:
        owner = session.get(Turn, row.turn_id) if row.turn_id else None
        if not owner or owner.conversation_id != conversation_id:
            # A pre-migration cross-session reference remains usable only in the
            # historical consumer that already received these exact input bytes.
            historical = row.origin_turn_id and any(str(row.id) in turn.reference_ids for turn in
                session.scalars(select(Turn).where(Turn.conversation_id == conversation_id)))
            if not historical:
                raise HTTPException(404, '图片不属于当前会话')
    return row


def picture_dto(row):
    return dict(id=str(row.id), name=row.name,
                url=f'{ROOT}/tasks/{row.task_id}/studio/pictures/{row.id}/content',
                width=row.width, height=row.height, turnId=str(row.turn_id or row.origin_turn_id),
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


def view(session, actor, task_id, conversation_id=None):
    task = access(session, actor, task_id)
    channel = conversation(session, task.id, conversation_id) if conversation_id else current_conversation(session, task.id)
    turns = []
    active = None
    query = select(Turn).where(Turn.task_id == task.id)
    if channel is not None:
        query = query.where(Turn.conversation_id == channel.id)
    for turn in session.scalars(query.order_by(Turn.created_at, Turn.id)):
        job = session.get(Job, turn.job_id)
        if job.status not in TERMINAL:
            active = str(turn.id)
        attachments = [asset(*attachment(session, task, identity)) for identity in turn.attachment_ids]
        result = job.result or {}
        order = {value: index for index, value in enumerate(result.get('deliveryOrder', []))}
        pictures = list(session.scalars(select(Picture).where(Picture.turn_id == turn.id)
            .order_by(Picture.created_at, Picture.id)))
        pictures.sort(key=lambda p: order.get(str(p.id), len(order)))
        turns.append(dict(id=str(turn.id), conversationId=str(turn.conversation_id),
            text=turn.text, skillName=turn.skill_name, deliveryError=turn.delivery_error,
            deliveryStatus=result.get('deliveryStatus'),
            status=job.status, reply=turn.reply, error=job.error, jobId=str(job.id),
            jobVersion=job.version, attachments=attachments,
            referencePictures=[picture_dto(picture(session, task, UUID(value)))
                               for value in turn.reference_ids],
            pictures=[picture_dto(p) for p in pictures],
            createdAt=turn.created_at))
    channels = conversations(session, task.id)
    record = available_archive(session, task.id)
    reopened = session.scalar(select(TaskEvent.id).where(TaskEvent.task_id == task.id,
        TaskEvent.kind == 'task.studio_reopened').limit(1)) is not None
    return dict(taskId=str(task.id), conversationId=str(channel.id) if channel else None,
        conversations=channels, maxConversations=10,
        activeConversationCount=sum(bool(row['activeTurnId']) for row in channels),
        completed=task.status == 'completed', taskVersion=task.version,
        archiveId=str(record.id) if record else None, reopened=reopened, turns=turns,
        materials=[asset(row, source) for row, source in visible(session, task.id, channel.id if channel else None)],
        skills=enabled_listing(session),
        activeTurnId=active)


def transcript(session, actor, task_id, after, conversation_id=None):
    access(session, actor, task_id)
    query = select(Transcript).where(Transcript.task_id == task_id, Transcript.id > after)
    channel = conversation(session, task_id, conversation_id) if conversation_id else current_conversation(session, task_id)
    if channel is not None:
        query = query.join(Turn, Turn.id == Transcript.turn_id).where(Turn.conversation_id == channel.id)
    rows = list(session.scalars(query.order_by(Transcript.id).limit(501)))
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


def conversation(session, task_id, identity, *, writable=False):
    row = session.get(Conversation, identity)
    receipt = session.get(ConversationDeletion, identity)
    if not row or row.task_id != task_id:
        raise HTTPException(410 if receipt and receipt.task_id == task_id else 404, '会话已删除或不存在')
    if writable and receipt:
        raise HTTPException(409, '会话正在删除或等待重试，不能修改')
    return row


def conversations(session, task_id):
    result = []
    for row in session.scalars(select(Conversation).where(Conversation.task_id == task_id)
            .order_by(Conversation.created_at, Conversation.id)):
        jobs = session.execute(select(Turn.id, Job.status).join(Job, Turn.job_id == Job.id)
            .where(Turn.conversation_id == row.id).order_by(Turn.created_at, Turn.id)).all()
        active = next((identity for identity, state in jobs if state not in TERMINAL), None)
        state = next((state for identity, state in jobs if identity == active), jobs[-1][1] if jobs else 'empty')
        receipt = session.get(ConversationDeletion, row.id)
        result.append(dict(id=str(row.id), name=row.name, version=row.version,
            createdAt=row.created_at.replace(tzinfo=timezone.utc), updatedAt=row.updated_at.replace(tzinfo=timezone.utc), turnCount=len(jobs),
            activeTurnId=str(active) if active else None,
            status='running' if state in ('collecting', 'cancelling', 'uncertain') else state,
            deletionStatus=receipt.status if receipt else None, deletionError=receipt.error if receipt else None))
    return result
