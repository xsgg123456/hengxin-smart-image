from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.contracts.business import PageResult, Template, TemplateInput, TemplateQuery
from app.db.session import get_session
from app.modules.auth.permissions import require_permission
from . import service

router = APIRouter(tags=['templates'])
SharedUser = Annotated[object, Depends(require_permission('shared_resources'))]
Database = Annotated[Session, Depends(get_session)]


@router.get('/templates', response_model=PageResult[Template])
def templates(query: Annotated[TemplateQuery, Query()], user: SharedUser, session: Database):
    return service.list_templates(session, query)


@router.get('/templates/{id}', response_model=Template)
def template(id: UUID, user: SharedUser, session: Database):
    return service.read_current(session, service.find_template(session, id))


@router.get('/templates/{id}/versions', response_model=list[Template])
def versions(id: UUID, user: SharedUser, session: Database):
    return service.list_versions(session, id)


@router.post('/templates', response_model=Template)
def create(body: TemplateInput, user: SharedUser, session: Database):
    return service.save_template(session, user, body)


@router.put('/templates/{id}', response_model=Template)
def update(id: UUID, body: TemplateInput, user: SharedUser, session: Database):
    return service.save_template(session, user, body, id)


@router.delete('/templates/{id}', status_code=204)
def delete(id: UUID, user: SharedUser, session: Database):
    service.delete_template(session, user, id)
