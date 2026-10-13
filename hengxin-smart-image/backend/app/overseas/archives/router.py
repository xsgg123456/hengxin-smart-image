from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.core.browser_auth import browser_request
from app.overseas.auth.dependencies import CurrentMember
from app.overseas.tasks.router import Database, Key
from app.overseas.pictures.schemas import ArchiveRequest
from app.storage.minio_store import get_store
from . import service

router = APIRouter(prefix='/api/overseas/v1', tags=['overseas-archives'])


@router.post('/tasks/{task_id}/archive', dependencies=[Depends(browser_request)])
def archive(task_id: UUID, body: ArchiveRequest, actor: CurrentMember, session: Database, idempotency_key: Key,
            store=Depends(get_store)):
    return service.archive(session, actor, task_id, body, idempotency_key, store)


@router.get('/archives')
def listing(actor: CurrentMember, session: Database, product: str = Query('', max_length=200),
            brand: str = Query('', max_length=200), sku: str = Query('', max_length=200),
            search: str = Query('', max_length=200), page: int = Query(1, ge=1),
            pageSize: int = Query(20, ge=1, le=100)):
    return service.listing(session, actor, product, brand, sku, search, page, pageSize)


@router.get('/archives/{archive_id}/download')
def download(archive_id: UUID, actor: CurrentMember, session: Database, store=Depends(get_store)):
    return service.download(session, store, actor, archive_id)


@router.get('/archives/{archive_id}')
def detail(archive_id: UUID, actor: CurrentMember, session: Database, store=Depends(get_store)):
    return service.view(session, store, actor, archive_id)


@router.get('/archives/{archive_id}/pictures/{picture_id}/content')
def content(archive_id: UUID, picture_id: UUID, actor: CurrentMember, session: Database, store=Depends(get_store)):
    return service.content(session, store, actor, archive_id, picture_id)
