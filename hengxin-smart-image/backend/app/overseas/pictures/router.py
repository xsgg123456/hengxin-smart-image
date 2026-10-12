from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.core.browser_auth import browser_request
from app.overseas.auth.dependencies import CurrentMember
from app.overseas.tasks.router import Database, Key
from app.storage.minio_store import get_store
from app.overseas.generation import service as generation
from . import queries, files, review, revisions
from .schemas import VersionRequest, RevisionRequest, RetryRequest

router = APIRouter(prefix='/api/overseas/v1', tags=['overseas-pictures'])


@router.get('/tasks/{task_id}/pictures')
def pictures(task_id: UUID, actor: CurrentMember, session: Database):
    return queries.listing(session, actor, task_id)


@router.get('/pictures/{picture_id}/versions/{version}/content')
def content(picture_id: UUID, version: int, actor: CurrentMember, session: Database,
            download: bool = False, store=Depends(get_store)):
    return files.content(session, store, actor, picture_id, version, download)


@router.post('/pictures/{picture_id}/approve', dependencies=[Depends(browser_request)])
def approve(picture_id: UUID, body: VersionRequest, actor: CurrentMember, session: Database, idempotency_key: Key):
    return review.approve(session, actor, picture_id, body, idempotency_key)


@router.post('/pictures/{picture_id}/revisions', dependencies=[Depends(browser_request)])
def revise(picture_id: UUID, body: RevisionRequest, actor: CurrentMember, session: Database, idempotency_key: Key):
    return revisions.revise(session, actor, picture_id, body, idempotency_key)


@router.post('/tasks/{task_id}/generation/retry', dependencies=[Depends(browser_request)])
def retry(task_id: UUID, body: RetryRequest, actor: CurrentMember, session: Database, idempotency_key: Key):
    return generation.retry(session, actor, task_id, body, idempotency_key)
