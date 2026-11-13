"""Read only the current member's workspace, messages and original files."""
from datetime import timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Job
from app.overseas.studio.image_edit_history import public_edits
from app.resource_models import UserRecord
from app.worker.leases import TERMINAL
from .bindings import read_bindings
from .conversation_models import Conversation, ConversationDeletion, Workspace
from .conversation_service import owned
from .file_service import asset
from .policy import require_workspace
from .skill_state import freeze_enabled
from .turn_models import OutputFile, Picture, Transcript, Turn, Upload
from .turn_service import picture, upload


def timestamp(value):
    if value is None:
        return None
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()


def picture_dto(row, workspace):
    return dict(id=str(row.id), name=row.name, url=f'/api/v1/domestic-studio/workspaces/{workspace}/pictures/{row.id}/content',
                width=row.width, height=row.height, turnId=str(row.turn_id), sku=None, archived=False,
                sourcePath=row.source_path)


def output_dto(row, workspace):
    return dict(id=str(row.id), name=row.name, contentType=row.content_type, sizeBytes=row.size_bytes,
                url=f'/api/v1/domestic-studio/workspaces/{workspace}/outputs/{row.id}/content')


def channel_rows(session, actor_id, workspace):
    channels = list(session.scalars(select(Conversation).where(Conversation.owner_id == actor_id,
        Conversation.workspace == workspace).order_by(Conversation.created_at, Conversation.id)))
    result = []
    for channel in channels:
        jobs = session.execute(select(Turn.id, Job.status).join(Job, Job.id == Turn.job_id)
            .where(Turn.conversation_id == channel.id).order_by(Turn.created_at, Turn.id)).all()
        active = next((identity for identity, status in jobs if status not in TERMINAL), None)
        status = next((status for identity, status in jobs if identity == active), jobs[-1][1] if jobs else 'empty')
        status = 'running' if status in ('uncertain', 'collecting', 'cancelling') else 'succeeded' if status == 'partial' else status
        receipt = session.get(ConversationDeletion, channel.id)
        result.append(dict(id=str(channel.id), name=channel.name, version=channel.version,
            createdAt=timestamp(channel.created_at), updatedAt=timestamp(channel.updated_at),
            activeTurnId=str(active) if active else None, status=status, turnCount=len(jobs),
            deletionStatus=receipt.status if receipt else None, deletionError=receipt.error if receipt else None))
    return channels, result


def available_skills(session, workspace, catalog):
    identity = read_bindings(session)[workspace]
    if not identity:
        return []
    try:
        frozen = freeze_enabled(session, catalog, identity)['skill']
        item = next((item for item in catalog.list() if item['id'] == frozen['id']), None)
        return [{**item, 'enabled': True, 'platforms': []}] if item else []
    except HTTPException:
        return []


def view(session, actor_id, workspace, conversation_id=None, *, catalog):
    require_workspace(workspace)
    channels, summaries = channel_rows(session, actor_id, workspace)
    channel = owned(session, actor_id, workspace, conversation_id, allow_deleting=True) if conversation_id else (channels[-1] if channels else None)
    deleting = bool(channel and session.get(ConversationDeletion, channel.id))
    results, active = [], None
    actor = session.get(UserRecord, actor_id)
    if channel and not deleting:
        rows = session.scalars(select(Turn).where(Turn.conversation_id == channel.id)
                               .order_by(Turn.created_at, Turn.id)).all()
        for turn in rows:
            job = session.get(Job, turn.job_id)
            if job is None or turn.actor_id != actor_id:
                raise HTTPException(503, '会话资料校验失败，请联系管理员')
            if job.status not in TERMINAL:
                active = str(turn.id)
            message = session.scalar(select(Transcript).where(Transcript.turn_id == turn.id,
                Transcript.kind == 'message', Transcript.text == turn.reply).order_by(Transcript.id.desc()).limit(1)) if turn.reply else None
            reply_time = message.created_at if message else turn.finished_at if turn.reply else None
            skill = turn.snapshot.get('skill') or {}
            results.append(dict(id=str(turn.id), conversationId=str(channel.id), text=turn.text,
                skillName=skill.get('displayName') or skill.get('name'),
                status=job.status, reply=turn.reply, error=turn.error or job.error, jobId=str(job.id), jobVersion=turn.version,
                canRecover=(job.status == 'uncertain' and turn.dispatched and bool(turn.process_identity)
                            and not turn.cancel_requested), recoveryRequested=turn.recovery_requested,
                actor=dict(id=str(actor_id), name=actor.name if actor else None), createdAt=timestamp(turn.created_at),
                replyAt=timestamp(reply_time), replyTimeSource=('message' if message else 'completed') if reply_time else None,
                attachments=[asset(upload(session, channel.id, identity), workspace) for identity in turn.snapshot.get('attachmentIds', [])],
                referencePictures=[picture_dto(picture(session, channel.id, UUID(identity)), workspace)
                                   for identity in turn.snapshot.get('referencePictureIds', [])],
                imageEdits=public_edits(turn.snapshot),
                pictures=[picture_dto(row, workspace) for row in session.scalars(select(Picture)
                    .where(Picture.turn_id == turn.id).order_by(Picture.created_at, Picture.id))],
                outputs=[output_dto(row, workspace) for row in session.scalars(select(OutputFile)
                    .where(OutputFile.turn_id == turn.id).order_by(OutputFile.created_at, OutputFile.id))]))
    state = session.get(Workspace, (actor_id, workspace))
    skills = available_skills(session, workspace, catalog)
    return dict(taskId=workspace, taskVersion=state.version if state else 1,
        conversationId=str(channel.id) if channel else None, conversations=summaries, maxConversations=10,
        activeConversationCount=sum(bool(row['activeTurnId']) for row in summaries), completed=False,
        reopened=False, archiveId=None, turns=results, activeTurnId=active, skills=skills,
        materials=[asset(row, workspace) for row in session.scalars(select(Upload).where(
            Upload.conversation_id == channel.id, Upload.status == 'ready').order_by(Upload.created_at, Upload.id))] if channel and not deleting else [],
        fixedSkillReady=bool(skills))


def transcript(session, actor_id, workspace, conversation_id, after):
    channel = owned(session, actor_id, workspace, conversation_id, allow_deleting=True)
    if session.get(ConversationDeletion, channel.id):
        return dict(items=[], cursor=after, hasMore=False)
    rows = list(session.scalars(select(Transcript).join(Turn, Turn.id == Transcript.turn_id).where(
        Turn.conversation_id == channel.id, Transcript.id > after).order_by(Transcript.id).limit(501)))
    more, rows = len(rows) > 500, rows[:500]
    return dict(items=[dict(id=row.id, turnId=str(row.turn_id), itemId=row.item_id, kind=row.kind,
        text=row.text, state=row.state, createdAt=timestamp(row.created_at)) for row in rows],
        cursor=rows[-1].id if rows else after, hasMore=more)
