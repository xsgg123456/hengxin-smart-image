"""Shared archive reads and creator-only archive requests for domestic Studio."""
from tempfile import SpooledTemporaryFile
from uuid import UUID
from zipfile import ZIP_STORED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.responses import StreamingResponse

from app.core.browser_auth import browser_request
from app.modules.files.delivery import FileDelivery
from app.overseas.attachment_delivery import deliver
from app.overseas.studio.files import copy_to
from app.storage.minio_store import get_store
from . import archive_deletion, archive_queries, archive_service, recovery_transport
from .router import Database, Key, User


router = APIRouter(prefix='/domestic-studio', tags=['domestic-studio-archives'])


@router.post('/workspaces/{workspace}/conversations/{conversation_id}/archive',
             dependencies=[Depends(browser_request)])
def archive(workspace: str, conversation_id: UUID, body: archive_service.ArchiveInput,
            actor: User, session: Database, key: Key):
    record = archive_service.prepare(session, actor.id, workspace, conversation_id, body, key)
    identity = record.id
    # Persist the exact destination manifest before writing independently owned bytes.
    session.commit()
    # The native owner serializes copying with source/archive deletion even if
    # the API's database connection drops during large object transfers.
    recovery_transport.request_archive(actor.id, identity, conversation_id)
    session.expire_all()
    return archive_queries.detail(session, identity)


@router.get('/archives')
def listing(actor: User, session: Database, search: str = Query('', max_length=200),
            workspace: str = '', page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100)):
    return archive_queries.listing(session, search, workspace, page, pageSize)


@router.get('/archives/{archive_id}')
def detail(archive_id: UUID, actor: User, session: Database):
    return archive_queries.detail(session, archive_id)


@router.delete('/archives/{archive_id}', dependencies=[Depends(browser_request)])
def remove(archive_id: UUID, actor: User, session: Database):
    result = archive_deletion.request(session, actor.id, archive_id)
    session.commit()
    return result


@router.get('/archives/{archive_id}/deletion')
def deletion_status(archive_id: UUID, actor: User, session: Database):
    return archive_deletion.status(session, actor, archive_id)


@router.get('/archives/{archive_id}/files/{file_id}/content')
@router.head('/archives/{archive_id}/files/{file_id}/content')
def content(archive_id: UUID, file_id: UUID, request: Request, actor: User, session: Database,
            preview: bool = False, thumbnail: bool = False, store=Depends(get_store)):
    row = archive_queries.file(session, archive_id, file_id)
    captured = FileDelivery.capture(row)
    session.close()
    return deliver(store, captured, head=request.method == 'HEAD', preview=preview or row.kind == 'picture',
                   thumbnail=thumbnail, if_none_match=request.headers.get('if-none-match'), verify_content=True)


@router.get('/archives/{archive_id}/download')
def download(archive_id: UUID, actor: User, session: Database, store=Depends(get_store)):
    record, manifest = archive_queries.verified(session, archive_id)
    rows = [row for row in manifest if row.kind == 'picture']
    output, total = SpooledTemporaryFile(max_size=8 * 1024 * 1024), 0
    try:
        with ZipFile(output, 'w', ZIP_STORED) as zipped:
            for index, row in enumerate(rows):
                total += row.size_bytes
                if total > 1024 * 1024 * 1024:
                    raise HTTPException(413, '归档超过 1 GiB 限制')
                extension = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}.get(row.content_type)
                if extension is None:
                    raise HTTPException(503, '归档图片类型无效')
                with zipped.open(f'{index + 1:03d}{extension}', 'w', force_zip64=True) as entry:
                    copy_to(store, row, entry)
    except Exception:
        output.close()
        raise
    output.seek(0)
    def chunks():
        try:
            while chunk := output.read(65536):
                yield chunk
        finally:
            output.close()
    return StreamingResponse(chunks(), media_type='application/zip', headers={
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': f'attachment; filename="archive-{record.id}.zip"'})
