"""Public conversation data with admin-scoped, conversation-bound file URLs."""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Job
from app.overseas.studio.image_edit_history import public_edits
from app.resource_models import UserRecord
from . import admin_queries
from .queries import timestamp
from .turn_models import OutputFile, Picture, Transcript, Turn, Upload

ROOT = '/api/v1/management/domestic-studio/sessions'


def submitted_upload_ids(session, channel_id):
    return {UUID(value.split(':', 1)[-1]) for snapshot in session.scalars(
        select(Turn.snapshot).where(Turn.conversation_id == channel_id))
        for value in snapshot.get('attachmentIds', [])}


def file_dto(row, channel_id, kind):
    data = dict(id=('upload:' if kind == 'files' else '') + str(row.id), name=row.name,
        contentType=row.content_type, sizeBytes=row.size_bytes,
        url=f'{ROOT}/{channel_id}/{kind}/{row.id}/content')
    if kind == 'files':
        data['source'] = 'upload'
    if kind == 'pictures':
        data.update(width=row.width, height=row.height, turnId=str(row.turn_id), sku=None, archived=False)
    return data


def file_row(session, channel_id, kind, identity):
    admin_queries.conversation(session, channel_id)
    if kind == 'files':
        if identity not in submitted_upload_ids(session, channel_id):
            raise HTTPException(404, '附件不存在或尚未提交')
        statement = select(Upload).where(Upload.id == identity, Upload.conversation_id == channel_id,
                                         Upload.status == 'ready')
    elif kind in ('pictures', 'outputs'):
        model = Picture if kind == 'pictures' else OutputFile
        statement = select(model).join(Turn, Turn.id == model.turn_id).where(
            model.id == identity, Turn.conversation_id == channel_id)
    else:
        raise HTTPException(404, '文件不存在或不可访问')
    row = session.scalar(statement)
    if row is None:
        raise HTTPException(404, '文件不存在或不可访问')
    return row


def references(session, channel, identities, kind):
    result = []
    for value in identities:
        identity = UUID(value.split(':', 1)[-1])
        try:
            result.append(file_dto(file_row(session, channel.id, kind, identity), channel.id, kind))
        except HTTPException as error:
            if error.status_code != 404:
                raise
            # Keep the submitted reference visible while access still returns 404.
            missing = dict(id=str(value), name='原文件已不可用', unavailable=True,
                url=f'{ROOT}/{channel.id}/{kind}/{identity}/content', contentType='', sizeBytes=0)
            missing.update(dict(source='upload') if kind == 'files' else
                           dict(width=0, height=0, turnId='', sku=None, archived=False))
            result.append(missing)
    return result


def detail(session, channel):
    owner = session.get(UserRecord, channel.owner_id)
    summaries = admin_queries.siblings(session, channel.owner_id)
    summary = next(row for row in summaries if row['id'] == str(channel.id))
    turns = []
    for turn in session.scalars(select(Turn).where(Turn.conversation_id == channel.id)
                               .order_by(Turn.created_at, Turn.id)):
        job = session.get(Job, turn.job_id)
        if job is None or turn.actor_id != channel.owner_id:
            raise HTTPException(503, '会话资料校验失败，请联系管理员')
        message = session.scalar(select(Transcript).where(Transcript.turn_id == turn.id,
            Transcript.kind == 'message', Transcript.text == turn.reply).order_by(Transcript.id.desc()).limit(1)) if turn.reply else None
        reply_at = message.created_at if message else turn.finished_at if turn.reply else None
        skill = turn.snapshot.get('skill') or {}
        turns.append(dict(id=str(turn.id), conversationId=str(channel.id), text=turn.text,
            skillName=skill.get('displayName') or skill.get('name'), status=job.status,
            reply=turn.reply, error='执行发生错误，请查看公开过程' if turn.error or job.error else None,
            jobId=str(job.id), jobVersion=turn.version, canRecover=False, recoveryRequested=turn.recovery_requested,
            actor=dict(id=str(channel.owner_id), name=owner.name if owner else None), createdAt=timestamp(turn.created_at),
            replyAt=timestamp(reply_at), replyTimeSource=('message' if message else 'completed') if reply_at else None,
            attachments=references(session, channel, turn.snapshot.get('attachmentIds', []), 'files'),
            referencePictures=references(session, channel, turn.snapshot.get('referencePictureIds', []), 'pictures'),
            imageEdits=public_edits(turn.snapshot),
            pictures=[file_dto(row, channel.id, 'pictures') for row in session.scalars(select(Picture)
                .where(Picture.turn_id == turn.id).order_by(Picture.created_at, Picture.id))],
            outputs=[file_dto(row, channel.id, 'outputs') for row in session.scalars(select(OutputFile)
                .where(OutputFile.turn_id == turn.id).order_by(OutputFile.created_at, OutputFile.id))]))
    workspace = dict(taskId=channel.workspace, taskVersion=channel.version, conversationId=str(channel.id),
        maxConversations=10,
        activeConversationCount=sum(bool(row['activeTurnId']) for row in summaries if row['workspace'] == channel.workspace),
        completed=False, reopened=False, archiveId=None, turns=turns, activeTurnId=summary['activeTurnId'],
        skills=[], fixedSkillReady=False, materials=[file_dto(row, channel.id, 'files')
            for row in session.scalars(select(Upload).where(Upload.conversation_id == channel.id,
                Upload.id.in_(submitted_upload_ids(session, channel.id)),
                Upload.status == 'ready').order_by(Upload.created_at, Upload.id))])
    return dict(session=summary, siblingSessions=summaries, workspace=workspace)


def transcript(session, channel, after):
    rows = list(session.scalars(select(Transcript).join(Turn, Turn.id == Transcript.turn_id).where(
        Turn.conversation_id == channel.id, Transcript.id > after).order_by(Transcript.id).limit(501)))
    more, rows = len(rows) > 500, rows[:500]
    return dict(items=[dict(id=row.id, turnId=str(row.turn_id), itemId=row.item_id, kind=row.kind,
        text=row.text, state=row.state, createdAt=timestamp(row.created_at)) for row in rows],
        cursor=rows[-1].id if rows else after, hasMore=more)
