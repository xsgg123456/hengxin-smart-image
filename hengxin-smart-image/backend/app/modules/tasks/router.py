from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session
from app.contracts import business as b
from app.db.session import get_session
from app.modules.auth.permissions import require_permission
from .service import create_task
from .queries import detail, list_tasks
from .cancellations import delete_task

router = APIRouter(tags=['tasks'])
SharedUser = Annotated[object, Depends(require_permission('shared_resources'))]
Database = Annotated[Session, Depends(get_session)]


@router.post('/tasks', response_model=b.Accepted, status_code=202)
def create(body: b.CreateTaskInput, user: SharedUser, session: Database,
           idempotency_key: Annotated[str, Header(min_length=1, max_length=128)]):
    return create_task(session, user, body, idempotency_key)


@router.get('/tasks', response_model=b.TaskPage)
def tasks(query: Annotated[b.TaskQuery, Query()], user: SharedUser, session: Database):
    return list_tasks(session, query)


@router.get('/tasks/{id}', response_model=b.TaskDetailData)
def task(id: UUID, user: SharedUser, session: Database):
    return detail(session, id)


@router.delete('/tasks/{id}', response_model=b.DeletionReceipt)
def delete(id: UUID, user: SharedUser, session: Database):
    return delete_task(session, user, id)
