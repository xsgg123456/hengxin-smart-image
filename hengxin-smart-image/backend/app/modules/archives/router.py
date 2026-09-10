from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.contracts import business as b
from app.db.session import get_session
from app.modules.auth.permissions import require_permission
from . import service

router = APIRouter(tags=['archives'])
SharedUser = Annotated[object, Depends(require_permission('shared_resources'))]
Database = Annotated[Session, Depends(get_session)]


@router.post('/tasks/{id}/archives', response_model=b.Archive)
def create(id: UUID, user: SharedUser, session: Database, body: b.ArchiveInput | None = None,
           idempotency_key: Annotated[str | None, Header(max_length=128)] = None):
    return service.create_archive(session, user, id, body, idempotency_key)


@router.get('/archives', response_model=b.PageResult[b.Archive])
def listing(query: Annotated[b.PageQuery, Query()], user: SharedUser, session: Database):
    return service.list_archives(session, query)


@router.get('/archives/{id}', response_model=b.Archive)
def detail(id: UUID, user: SharedUser, session: Database):
    return service.serialize(session, service.find_archive(session, id))


@router.delete('/archives/{id}', status_code=204)
def delete(id: UUID, user: SharedUser, session: Database):
    service.delete_archive(session, user, id)
