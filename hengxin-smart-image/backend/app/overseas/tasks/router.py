from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session
from app.core.browser_auth import browser_request
from app.db.session import get_session
from app.overseas.auth.dependencies import CurrentMember
from app.overseas.permissions import authorize_member
from . import assignment, queries, service
from .schemas import Assignment, CreateTask

router = APIRouter(prefix='/api/overseas/v1', tags=['overseas-tasks'])
Database = Annotated[Session, Depends(get_session)]
Key = Annotated[str, Header(alias='Idempotency-Key', min_length=1, max_length=128)]


@router.post('/tasks', status_code=201, dependencies=[Depends(browser_request)])
def create(body: CreateTask, actor: CurrentMember, session: Database, response: Response, idempotency_key: Key):
    result, created = service.create_task(session, actor, body, idempotency_key)
    response.status_code = 201 if created else 200
    return result


@router.get('/tasks')
def tasks(actor: CurrentMember, session: Database, search: str = Query('', max_length=100),
          scope: Literal['all', 'mine'] = 'all', status: str | None = Query(None, max_length=40),
          page: int = Query(1, ge=1), page_size: int = Query(20, alias='pageSize', ge=1, le=100)):
    authorize_member(session, actor, 'task.read')
    return queries.list_tasks(session, actor, search, scope, status, page, page_size)


@router.get('/task-designers')
def designers(actor: CurrentMember, session: Database, search: str = Query('', max_length=100),
              page: int = Query(1, ge=1), page_size: int = Query(20, alias='pageSize', ge=1, le=100)):
    return queries.designers(session, actor, search, page, page_size)


@router.get('/tasks/{task_id}')
def detail(task_id: UUID, actor: CurrentMember, session: Database):
    return queries.detail(session, task_id, actor)


@router.patch('/tasks/{task_id}/assignment', dependencies=[Depends(browser_request)])
def assign(task_id: UUID, body: Assignment, actor: CurrentMember, session: Database, idempotency_key: Key):
    return assignment.assign(session, actor, task_id, body, idempotency_key)
