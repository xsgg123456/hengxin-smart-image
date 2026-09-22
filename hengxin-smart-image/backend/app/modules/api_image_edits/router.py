from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.db.session import get_session
from app.modules.auth.permissions import require_permission
from app.modules.files.multipart import UPLOAD_BODY, parse_upload
from app.modules.files.streaming import OwnedStreamResponse
from app.modules.files.validation import validate_image
from app.storage.minio_store import get_store
from . import control, files, service, versions, zip_download
from .config import get_api_settings
from .models import ApiChannel
from .presentation import list_tasks, task_view
from .schemas import CreateTask, ResolveTask, ReviseItem, RestoreVersion

router = APIRouter(prefix='/api-image-edits', tags=['api-image-edits'])
User = Annotated[object, Depends(require_permission('shared_resources'))]
Admin = Annotated[object, Depends(require_permission('manage_system'))]
Database = Annotated[Session, Depends(get_session)]
Key = Annotated[str, Header(alias='Idempotency-Key', min_length=1, max_length=128)]


@router.get('/status')
def status(user: User, session: Database):
    gate = session.get(ApiChannel, 1)
    return {'enabled': get_api_settings().enabled, 'paused': bool(gate and gate.paused),
            'reason': gate.reason if gate else None}


@router.post('/files', openapi_extra=UPLOAD_BODY)
async def upload(request: Request, user: User, session: Database, store=Depends(get_store)):
    service.enabled()
    form, file = await parse_upload(request)
    try:
        image = await run_in_threadpool(validate_image, file)
        record = await run_in_threadpool(files.save_upload, session, store, user, image)
        return files.picture(record)
    finally:
        await form.close()


@router.get('/files/{file_id}')
def metadata(file_id: UUID, user: User, session: Database):
    return files.picture(files.find_file(session, file_id))


@router.get('/files/{file_id}/content')
def content(file_id: UUID, user: User, session: Database, download: bool = False,
            store=Depends(get_store)):
    record = files.find_file(session, file_id)
    try:
        stream = store.open(record)
    except Exception:
        raise HTTPException(503, '图片暂时不可读取') from None
    disposition = 'attachment' if download else 'inline'
    return OwnedStreamResponse(stream, media_type=record.content_type, headers={
        'Content-Length': str(record.size_bytes), 'Cache-Control': 'private, no-store',
        'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': f"{disposition}; filename=image; filename*=UTF-8''{quote(record.name, safe='')}",
    })


@router.delete('/files/{file_id}')
def delete_file(file_id: UUID, user: User, session: Database):
    files.delete_file(session, file_id, user)
    return {'deleted': True}


@router.post('/tasks', status_code=202)
def create(data: CreateTask, user: User, session: Database, key: Key):
    return {'taskId': str(service.submit(session, user, data, key))}


@router.get('/tasks')
def tasks(user: User, session: Database, page: int = Query(1, ge=1),
          pageSize: int = Query(20, ge=1, le=100), search: str = Query('', max_length=60),
          status: str = Query('', max_length=30)):
    return list_tasks(session, page, pageSize, search, status)


@router.get('/tasks/{task_id}')
def detail(task_id: UUID, user: User, session: Database):
    return task_view(session, service.find_task(session, task_id))


@router.post('/tasks/{task_id}/retry', status_code=202)
def retry(task_id: UUID, user: User, session: Database, key: Key):
    return {'taskId': str(service.retry(session, user, task_id, key))}


@router.delete('/tasks/{task_id}')
def delete(task_id: UUID, user: User, session: Database):
    service.delete_task(session, user, task_id)
    return {'deleted': True}


@router.post('/tasks/{task_id}/resolve')
def resolve(task_id: UUID, data: ResolveTask, user: Admin, session: Database):
    control.resolve(session, user, task_id, data.confirmedStopped)
    return {'taskId': str(task_id)}


@router.post('/channel/resume')
def resume(user: Admin, session: Database):
    control.resume(session, user)
    return {'resumed': True}


@router.post('/tasks/{task_id}/items/{item_id}/revise', status_code=202)
def revise_item(task_id: UUID, item_id: UUID, data: ReviseItem, user: User, session: Database, key: Key):
    return {'taskId': str(versions.revise(session, user, task_id, item_id, data, key))}


@router.post('/tasks/{task_id}/items/{item_id}/retry', status_code=202)
def retry_item(task_id: UUID, item_id: UUID, user: User, session: Database, key: Key):
    return {'taskId': str(versions.retry_item(session, user, task_id, item_id, key))}


@router.post('/tasks/{task_id}/items/{item_id}/restore')
def restore_item(task_id: UUID, item_id: UUID, data: RestoreVersion, user: User, session: Database, key: Key):
    return {'taskId': str(versions.restore(session, user, task_id, item_id, data, key))}


@router.get('/tasks/{task_id}/zip')
def download_zip(task_id: UUID, user: User, session: Database, store=Depends(get_store)):
    return zip_download.download(session, store, task_id)
