"""Domestic member-scoped Studio endpoints; no client-selected Skill."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from app.core.browser_auth import browser_request
from app.db.session import get_session
from app.modules.auth.permissions import require_permission
from app.modules.files.delivery import FileDelivery
from app.modules.files.multipart import UPLOAD_BODY, parse_upload
from app.overseas.attachment_delivery import deliver
from app.overseas.studio.files import MAX_BYTES
from app.overseas.studio.schemas import Cancel, DeleteConversation, NewConversation, RenameConversation, Send
from app.overseas.studio.recovery_router import RecoverFiles
from app.storage.minio_store import get_store
from . import conversation_deletion, conversation_service, file_service, queries, recovery_transport, turn_service
from .conversation_models import Conversation
from .management_router import get_catalog
from .policy import require_workspace
from .turn_models import Turn


router = APIRouter(prefix='/domestic-studio/workspaces/{workspace}', tags=['domestic-studio'])
User = Annotated[object, Depends(require_permission('shared_resources'))]
Database = Annotated[Session, Depends(get_session)]
Key = Annotated[str, Header(alias='Idempotency-Key', min_length=1, max_length=128)]
WRITE = [Depends(browser_request)]


def current(session, actor_id, workspace, turn_id):
    channel = session.scalar(select(Conversation.id).join(Turn, Turn.conversation_id == Conversation.id).where(
        Turn.id == turn_id, Conversation.owner_id == actor_id, Conversation.workspace == workspace))
    if channel is None:
        raise HTTPException(404, '轮次不存在')
    return channel


@router.get('')
def view(workspace: str, actor: User, session: Database, conversationId: UUID | None = None,
         catalog=Depends(get_catalog)):
    return queries.view(session, actor.id, workspace, conversationId, catalog=catalog)


@router.get('/transcript')
def transcript(workspace: str, actor: User, session: Database, after: int = Query(0, ge=0),
               conversationId: UUID | None = None):
    require_workspace(workspace)
    if conversationId is None:
        channels, _ = queries.channel_rows(session, actor.id, workspace)
        if not channels:
            return dict(items=[], cursor=after, hasMore=False)
        conversationId = channels[-1].id
    return queries.transcript(session, actor.id, workspace, conversationId, after)


@router.post('/conversations', dependencies=WRITE)
def create(workspace: str, body: NewConversation, actor: User, session: Database, key: Key,
           catalog=Depends(get_catalog)):
    channel = conversation_service.create(session, actor.id, workspace, body, key)
    result = queries.view(session, actor.id, workspace, channel.id, catalog=catalog)
    session.commit()
    return result


@router.patch('/conversations/{conversation_id}', dependencies=WRITE)
def rename(workspace: str, conversation_id: UUID, body: RenameConversation, actor: User,
           session: Database, key: Key, catalog=Depends(get_catalog)):
    channel = conversation_service.rename(session, actor.id, workspace, conversation_id, body, key)
    result = queries.view(session, actor.id, workspace, channel.id, catalog=catalog)
    session.commit()
    return result


@router.delete('/conversations/{conversation_id}', dependencies=WRITE)
def delete_conversation(workspace: str, conversation_id: UUID, body: DeleteConversation,
                        actor: User, session: Database, key: Key, catalog=Depends(get_catalog)):
    receipt = conversation_deletion.request(session, actor.id, workspace, conversation_id, body.version)
    result = queries.view(session, actor.id, workspace,
                          None if receipt['status'] == 'deleted' else conversation_id, catalog=catalog)
    session.commit()
    return result


@router.get('/conversations/{conversation_id}/deletion')
def deletion_status(workspace: str, conversation_id: UUID, actor: User, session: Database):
    return conversation_deletion.status(session, actor.id, workspace, conversation_id)


@router.post('/turns', dependencies=WRITE)
def send(workspace: str, body: Send, actor: User, session: Database, key: Key,
         conversationId: UUID | None = None, catalog=Depends(get_catalog)):
    channel_id = body.conversationId or conversationId
    if channel_id is None or (body.conversationId and conversationId and body.conversationId != conversationId):
        raise HTTPException(422, '请选择当前会话')
    channel = turn_service.send(session, actor.id, workspace, channel_id, body, key, catalog)
    result = queries.view(session, actor.id, workspace, channel.id, catalog=catalog)
    session.commit()
    return result


@router.post('/turns/{turn_id}/cancel', dependencies=WRITE)
def cancel(workspace: str, turn_id: UUID, body: Cancel, actor: User, session: Database,
           catalog=Depends(get_catalog)):
    channel_id = current(session, actor.id, workspace, turn_id)
    channel = turn_service.cancel(session, actor.id, workspace, channel_id, turn_id, body.version)
    result = queries.view(session, actor.id, workspace, channel.id, catalog=catalog)
    session.commit()
    return result


@router.post('/turns/{turn_id}/recover', dependencies=WRITE)
def recover(workspace: str, turn_id: UUID, body: Cancel, actor: User, session: Database,
            catalog=Depends(get_catalog)):
    channel_id = current(session, actor.id, workspace, turn_id)
    channel = turn_service.request_recovery(session, actor.id, workspace, channel_id, turn_id, body.version)
    result = queries.view(session, actor.id, workspace, channel.id, catalog=catalog)
    session.commit()
    return result


@router.get('/conversations/{conversation_id}/recoverable-files')
def recoverable_files(workspace: str, conversation_id: UUID, actor: User, session: Database):
    try:
        conversation_service.owned(session, actor.id, workspace, conversation_id)
    finally:
        session.rollback()
    return recovery_transport.request('available', actor.id, conversation_id)


@router.post('/conversations/{conversation_id}/recover-files', dependencies=WRITE)
def recover_files(workspace: str, conversation_id: UUID, body: RecoverFiles, actor: User, session: Database):
    try:
        conversation_service.owned(session, actor.id, workspace, conversation_id)
    finally:
        session.rollback()
    return recovery_transport.request('receive', actor.id, conversation_id, body.files)


@router.post('/files', dependencies=WRITE, openapi_extra=UPLOAD_BODY)
async def upload(request: Request, workspace: str, actor: User, session: Database,
                 conversationId: UUID, store=Depends(get_store)):
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    actor_id = actor.id
    await run_in_threadpool(session.rollback)
    await run_in_threadpool(file_service.authorize_upload, factory, actor_id, workspace, conversationId)
    form, file = await parse_upload(request, MAX_BYTES, maximum=MAX_BYTES, label='附件', size_label='500 MB')
    try:
        result = await run_in_threadpool(file_service.upload, factory, store, actor_id, workspace,
                                         conversationId, file.file, file.filename)
        return result
    finally:
        await form.close()


def content(session, store, actor, workspace, identity, *, kind, request, head=False, preview=False, thumbnail=False):
    row = (file_service.find(session, actor.id, workspace, identity) if kind == 'files' else
           file_service.find_output(session, actor.id, workspace, identity, picture=kind == 'pictures'))
    captured = FileDelivery.capture(row)
    session.close()
    return deliver(store, captured, head=head, preview=preview or kind == 'pictures',
                   thumbnail=thumbnail, if_none_match=request.headers.get('if-none-match'))


@router.get('/{kind}/{file_id}/content')
@router.head('/{kind}/{file_id}/content')
def read_file(workspace: str, kind: str, file_id: UUID, request: Request, actor: User, session: Database,
              preview: bool = False, thumbnail: bool = False, store=Depends(get_store)):
    if kind not in ('files', 'pictures', 'outputs'):
        raise HTTPException(404, '文件不存在')
    return content(session, store, actor, workspace, file_id, kind=kind, request=request,
                   head=request.method == 'HEAD', preview=preview, thumbnail=thumbnail)
