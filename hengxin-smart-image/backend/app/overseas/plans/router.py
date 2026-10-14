from uuid import UUID
from fastapi import APIRouter, Depends
from app.core.browser_auth import browser_request
from app.storage.minio_store import get_store
from app.overseas.auth.dependencies import CurrentMember
from app.overseas.tasks.router import Database, Key
from . import service
from .schemas import AnalysisRequest, ConfirmRequest

router = APIRouter(prefix='/api/overseas/v1', tags=['overseas-plans'])


@router.get('/tasks/{task_id}/plans')
def history(task_id: UUID, actor: CurrentMember, session: Database):
    return service.history(session, actor, task_id)


@router.post('/tasks/{task_id}/analysis', dependencies=[Depends(browser_request)])
def analysis(task_id: UUID, body: AnalysisRequest, actor: CurrentMember, session: Database,
           idempotency_key: Key, store=Depends(get_store)):
    return service.analyze(session, actor, task_id, body, idempotency_key, store)


@router.post('/tasks/{task_id}/plans/{plan_id}/confirm', dependencies=[Depends(browser_request)])
def confirm(task_id: UUID, plan_id: UUID, body: ConfirmRequest, actor: CurrentMember,
            session: Database, idempotency_key: Key):
    return service.confirm(session, actor, task_id, plan_id, body, idempotency_key)
