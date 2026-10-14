from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response
from starlette.concurrency import run_in_threadpool
from app.core.browser_auth import browser_request
from app.modules.files.multipart import parse_upload, UPLOAD_BODY
from app.overseas.auth.dependencies import CurrentMember
from app.overseas.permissions import authorize_member
from app.overseas.tasks.router import Database, Key
from app.storage.minio_store import get_store
from . import files, service
from .schemas import SubmitMaterials

router = APIRouter(prefix='/api/overseas/v1', tags=['overseas-materials'])


@router.post('/materials', status_code=201, dependencies=[Depends(browser_request)], openapi_extra=UPLOAD_BODY)
async def upload(request: Request, actor: CurrentMember, session: Database,
                 kind: Literal['requirement', 'competitor'], store=Depends(get_store)):
    await run_in_threadpool(authorize_member, session, actor, 'task.create')
    form, file = await parse_upload(request, files.MAX_BYTES, maximum=files.MAX_BYTES, label='资料', size_label='500 MB')
    try:
        data = await file.read(files.MAX_BYTES + 1)
        return await run_in_threadpool(files.save_upload, session, store, actor, data, file.filename, kind)
    finally:
        await form.close()


@router.get('/materials/{material_id}')
def metadata(material_id: UUID, actor: CurrentMember, session: Database):
    return service.describe(session, service.readable(session, material_id, actor))


@router.delete('/materials/{material_id}', status_code=204, dependencies=[Depends(browser_request)])
def delete(material_id: UUID, actor: CurrentMember, session: Database, store=Depends(get_store)):
    files.delete(session, store, actor, material_id)
    return Response(status_code=204)


@router.get('/materials/{material_id}/content')
def content(material_id: UUID, actor: CurrentMember, session: Database,
            store=Depends(get_store)):
    return files.content(session, store, actor, material_id)


@router.head('/materials/{material_id}/content')
def preflight(material_id: UUID, actor: CurrentMember, session: Database, store=Depends(get_store)):
    return files.content(session, store, actor, material_id, head=True)


@router.get('/tasks/{task_id}/materials')
def materials(task_id: UUID, actor: CurrentMember, session: Database):
    return service.for_task(session, actor, task_id)


@router.post('/tasks/{task_id}/materials', dependencies=[Depends(browser_request)])
def submit(task_id: UUID, body: SubmitMaterials, actor: CurrentMember, session: Database, idempotency_key: Key):
    return service.submit(session, actor, task_id, body, idempotency_key)
