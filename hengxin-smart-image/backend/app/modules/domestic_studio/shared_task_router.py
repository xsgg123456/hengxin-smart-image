"""Read a domestic task within its business entry using submitted content projections."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select

from app.modules.files.delivery import FileDelivery
from app.overseas.attachment_delivery import deliver
from app.storage.minio_store import get_store
from . import admin_details, admin_queries, task_queries
from .conversation_models import Conversation
from .router import Database, User
from .task_models import Task
from .workspaces import WorkspaceName

router = APIRouter(prefix='/{task_id}/view/{workspace}', tags=['domestic-task-view'])


def scoped_task(task_id: UUID, workspace: WorkspaceName, actor: User, session: Database, response: Response):
    row = session.scalar(select(Task).where(Task.id == task_id, Task.workspace == workspace,
        Task.deletion_status.is_distinct_from('deleted')))
    if row is None:
        raise HTTPException(404, '任务不存在或不属于当前业务')
    response.headers['Cache-Control'] = 'private, no-store'
    return row


ViewedTask = Annotated[Task, Depends(scoped_task)]


def scoped_session(conversation_id: UUID, task: ViewedTask, session: Database):
    row = session.scalar(select(Conversation).where(Conversation.id == conversation_id,
        Conversation.task_id == task.id, Conversation.workspace == task.workspace,
        Conversation.owner_id == task.owner_id, *admin_queries.readable()))
    if row is None:
        raise HTTPException(404, '会话不存在或不属于当前任务')
    return row


ViewedSession = Annotated[Conversation, Depends(scoped_session)]


@router.get('')
def detail(task: ViewedTask, session: Database, actor: User):
    return dict(task=task_queries.detail(session, task.id),
        sessions=[] if task.owner_id == actor.id else admin_queries.siblings(session, task.owner_id, task_id=task.id))


@router.get('/sessions/{conversation_id}')
def session_detail(channel: ViewedSession, session: Database):
    root = f'/api/v1/domestic-studio/tasks/{channel.task_id}/view/{channel.workspace}/sessions'
    return admin_details.detail(session, channel, root=root)


@router.get('/sessions/{conversation_id}/transcript')
def transcript(channel: ViewedSession, session: Database, after: int = Query(0, ge=0)):
    return admin_details.transcript(session, channel, after)


@router.get('/sessions/{conversation_id}/{kind}/{file_id}/content')
@router.head('/sessions/{conversation_id}/{kind}/{file_id}/content')
def content(channel: ViewedSession, session: Database, kind: str, file_id: UUID, request: Request,
            preview: bool = False, thumbnail: bool = False, store=Depends(get_store)):
    row = admin_details.file_row(session, channel.id, kind, file_id)
    captured = FileDelivery.capture(row)
    session.close()
    response = deliver(store, captured, head=request.method == 'HEAD', preview=preview or kind == 'pictures',
                       thumbnail=thumbnail, if_none_match=request.headers.get('if-none-match'))
    response.headers['Cache-Control'] = 'private, no-store'
    return response
