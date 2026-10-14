from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from starlette.concurrency import run_in_threadpool
from app.modules.files.multipart import parse_upload, UPLOAD_BODY
from app.overseas.permissions import authorize_member
from app.core.browser_auth import browser_request
from app.overseas.auth.dependencies import CurrentMember
from app.overseas.tasks.router import Database, Key
from app.storage.minio_store import get_store
from . import service, queries, files
from .schemas import Send, Cancel, ArchiveRequest, Complete

router = APIRouter(prefix='/api/overseas/v1/tasks/{task_id}/studio', tags=['overseas-studio'])
WRITE = [Depends(browser_request)]


@router.get('')
def view(task_id: UUID, actor: CurrentMember, session: Database):
    return queries.view(session, actor, task_id)


@router.get('/events')
def events(task_id: UUID, actor: CurrentMember, session: Database, after: int = Query(0, ge=0)):
    return queries.events(session, actor, task_id, after)


@router.post('/turns', dependencies=WRITE)
def send(task_id: UUID, body: Send, actor: CurrentMember, session: Database, idempotency_key: Key):
    return service.send(session, actor, task_id, body, idempotency_key)


@router.post('/conversations', dependencies=WRITE)
def new_conversation(task_id: UUID, body: Complete, actor: CurrentMember, session: Database, idempotency_key: Key):
    return service.new_conversation(session, actor, task_id, body, idempotency_key)


@router.get('/transcript')
def transcript(task_id: UUID, actor: CurrentMember, session: Database, after: int = Query(0, ge=0)):
    return queries.transcript(session, actor, task_id, after)


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


@router.post('/files', dependencies=WRITE, openapi_extra=UPLOAD_BODY)
async def upload(request: Request, task_id: UUID, actor: CurrentMember, session: Database,
                 store=Depends(get_store)):
    await run_in_threadpool(authorize_member, session, actor, 'task.design')
    form, file = await parse_upload(request, files.MAX_BYTES, maximum=files.MAX_BYTES, label='附件', size_label='500 MB')
    try:
        data = await file.read(files.MAX_BYTES + 1)
        return await run_in_threadpool(files.upload, session, store, actor, task_id, data, file.filename)
    finally:
        await form.close()


@router.get('/files/{file_id}/content')
def content(task_id: UUID, file_id: UUID, actor: CurrentMember, session: Database, store=Depends(get_store)):
    return files.content(session, store, actor, task_id, file_id)


@router.head('/files/{file_id}/content')
def preflight(task_id: UUID, file_id: UUID, actor: CurrentMember, session: Database, store=Depends(get_store)):
    return files.content(session, store, actor, task_id, file_id, head=True)


@router.get('/pictures/{picture_id}/content')
def picture(task_id: UUID, picture_id: UUID, actor: CurrentMember, session: Database, store=Depends(get_store)):
    return files.content(session, store, actor, task_id, picture_id, True)
