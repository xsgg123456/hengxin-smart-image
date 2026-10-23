from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from starlette.concurrency import run_in_threadpool
from app.modules.files.multipart import parse_upload, UPLOAD_BODY
from app.overseas.permissions import authorize_member
from app.core.browser_auth import browser_request
from app.overseas.auth.dependencies import CurrentMember
from app.overseas.tasks.router import Database, Key
from app.storage.minio_store import get_store
from . import service, queries, files, material_list, conversations
from .schemas import Send, Cancel, ArchiveRequest, Complete, NewConversation, RenameConversation, DeleteConversation

router = APIRouter(prefix='/api/overseas/v1/tasks/{task_id}/studio', tags=['overseas-studio'])
WRITE = [Depends(browser_request)]


@router.get('')
def view(task_id: UUID, actor: CurrentMember, session: Database, conversationId: UUID | None = None):
    return queries.view(session, actor, task_id, conversationId)


@router.get('/events')
def events(task_id: UUID, actor: CurrentMember, session: Database, after: int = Query(0, ge=0)):
    return queries.events(session, actor, task_id, after)


@router.delete('/materials/{identity}', dependencies=WRITE)
def remove_material(task_id: UUID, identity: str, actor: CurrentMember, session: Database, conversationId: UUID | None = None):
    return material_list.remove(session, actor, task_id, identity, conversationId)


@router.post('/turns', dependencies=WRITE)
def send(task_id: UUID, body: Send, actor: CurrentMember, session: Database, idempotency_key: Key,
         conversationId: UUID | None = None):
    return service.send(session, actor, task_id, body, idempotency_key, conversationId)


@router.post('/conversations', dependencies=WRITE)
def new_conversation(task_id: UUID, body: NewConversation, actor: CurrentMember, session: Database, idempotency_key: Key):
    return service.new_conversation(session, actor, task_id, body, idempotency_key)


@router.patch('/conversations/{conversation_id}', dependencies=WRITE)
def rename_conversation(task_id: UUID, conversation_id: UUID, body: RenameConversation,
                        actor: CurrentMember, session: Database, idempotency_key: Key):
    return conversations.rename(session, actor, task_id, conversation_id, body, idempotency_key)


@router.delete('/conversations/{conversation_id}', dependencies=WRITE)
def delete_conversation(task_id: UUID, conversation_id: UUID, body: DeleteConversation,
                        actor: CurrentMember, session: Database, idempotency_key: Key):
    return conversations.remove(session, actor, task_id, conversation_id, body, idempotency_key)


@router.get('/transcript')
def transcript(task_id: UUID, actor: CurrentMember, session: Database, after: int = Query(0, ge=0), conversationId: UUID | None = None):
    return queries.transcript(session, actor, task_id, after, conversationId)


@router.post('/turns/{turn_id}/cancel', dependencies=WRITE)
def cancel(task_id: UUID, turn_id: UUID, body: Cancel, actor: CurrentMember, session: Database):
    return service.cancel(session, actor, task_id, turn_id, body.version)


@router.post('/archive', dependencies=WRITE)
def archive(task_id: UUID, body: ArchiveRequest, actor: CurrentMember, session: Database, idempotency_key: Key,
            store=Depends(get_store)):
    return service.archive(session, actor, task_id, body, idempotency_key, store)


@router.post('/complete', dependencies=WRITE)
def complete(task_id: UUID, body: Complete, actor: CurrentMember, session: Database, idempotency_key: Key):
    return service.complete(session, actor, task_id, body, idempotency_key)


@router.post('/reopen', dependencies=WRITE)
def reopen(task_id: UUID, body: Complete, actor: CurrentMember, session: Database, idempotency_key: Key):
    return service.reopen(session, actor, task_id, body, idempotency_key)


@router.post('/files', dependencies=WRITE, openapi_extra=UPLOAD_BODY)
async def upload(request: Request, task_id: UUID, actor: CurrentMember, session: Database,
                 conversationId: UUID | None = None, store=Depends(get_store)):
    await run_in_threadpool(authorize_member, session, actor, 'task.design')
    form, file = await parse_upload(request, files.MAX_BYTES, maximum=files.MAX_BYTES, label='附件', size_label='500 MB')
    try:
        data = await file.read(files.MAX_BYTES + 1)
        return await run_in_threadpool(files.upload, session, store, actor, task_id, data, file.filename, conversationId)
    finally:
        await form.close()


@router.get('/files/{file_id}/content')
def content(task_id: UUID, file_id: UUID, actor: CurrentMember, session: Database,
            store=Depends(get_store), preview: bool = False):
    return files.content(session, store, actor, task_id, file_id, preview=preview)


@router.head('/files/{file_id}/content')
def preflight(task_id: UUID, file_id: UUID, actor: CurrentMember, session: Database,
              store=Depends(get_store), preview: bool = False):
    return files.content(session, store, actor, task_id, file_id, head=True, preview=preview)


@router.get('/pictures/{picture_id}/content')
def picture(task_id: UUID, picture_id: UUID, actor: CurrentMember, session: Database, store=Depends(get_store)):
    return files.content(session, store, actor, task_id, picture_id, True)


@router.head('/pictures/{picture_id}/content')
def picture_preflight(task_id: UUID, picture_id: UUID, actor: CurrentMember, session: Database,
                      store=Depends(get_store)):
    return files.content(session, store, actor, task_id, picture_id, True, head=True)
