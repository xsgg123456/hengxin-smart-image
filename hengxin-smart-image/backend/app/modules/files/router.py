from typing import Annotated
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.contracts.business import Picture
from app.db.session import get_session
from app.modules.auth.permissions import require_permission
from app.modules.files.service import find_file, save_upload
from app.modules.files.delivery import FileDelivery
from app.modules.files.variant_delivery import deliver_variant
from app.modules.files.internal_delivery import internal_delivery, head_delivery
from app.modules.files.streaming import OwnedStreamResponse
from app.modules.files.validation import validate_image
from app.modules.files.multipart import UPLOAD_BODY, parse_upload
from app.storage.minio_store import get_store

router = APIRouter(tags=['files'])
SharedUser = Annotated[object, Depends(require_permission('shared_resources'))]
Database = Annotated[Session, Depends(get_session)]


def picture(record):
    return Picture(name=record.name, url=f'/api/v1/files/{record.id}/content', fileId=str(record.id))


@router.post('/files', response_model=Picture, response_model_exclude_unset=True,
             openapi_extra=UPLOAD_BODY)
async def upload(request: Request, user: SharedUser, session: Database, store=Depends(get_store)):
    from app.modules.management.settings import values
    limit = (await run_in_threadpool(values, session))['maxUploadBytes']
    form, file = await parse_upload(request, limit)
    try:
        image = await run_in_threadpool(validate_image, file, limit)
        record = await run_in_threadpool(save_upload, session, store, user, image)
        return picture(record)
    finally:
        await form.close()


@router.get('/files/{file_id}', response_model=Picture, response_model_exclude_unset=True)
def metadata(file_id: UUID, user: SharedUser, session: Database):
    return picture(find_file(session, file_id))


@router.get('/files/{file_id}/content')
@router.head('/files/{file_id}/content')
def content(file_id: UUID, request: Request, user: SharedUser, session: Database, download: bool = False,
            store=Depends(get_store), variant: Literal['256', '1024'] | None = None):
    record = FileDelivery.capture(find_file(session, file_id))
    if variant is not None and not download:
        return deliver_variant(session, record, 'originals', int(variant), request, store)
    # Auth and business dependencies share this session; release both before storage I/O.
    session.close()
    accelerated = internal_delivery(record, store, request, 'originals', download)
    if accelerated is not None:
        return accelerated
    if request.method == 'HEAD':
        return head_delivery(record, store, download)
    try:
        stream = store.open(record)
    except Exception:
        raise HTTPException(503, '图片暂时不可读取，请稍后重试') from None
    disposition = 'attachment' if download else 'inline'
    return OwnedStreamResponse(stream, media_type=record.content_type, headers={
        'Content-Length': str(record.size_bytes),
        'Content-Disposition': f"{disposition}; filename=\"image\"; filename*=UTF-8''{quote(record.name, safe='')}",
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
    })
