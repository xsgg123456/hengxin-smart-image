from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.core.browser_auth import browser_request
from app.overseas.auth.dependencies import CurrentMember
from app.overseas.tasks.router import Database
from app.overseas.permissions import authorize_member
from . import read, service, source
from .schemas import SaveDraft, SelectSource, VersionBody
from .selection import select_source

router = APIRouter(prefix='/api/overseas/v1', tags=['overseas-requirement-drafts'])
protected = [Depends(browser_request)]


@router.get('/requirement-source')
def lookup(actor: CurrentMember, session: Database, sku: str = Query(min_length=1, max_length=80)):
    authorize_member(session, actor, 'task.create')
    sku = sku.strip()
    from fastapi import HTTPException
    if not sku:
        raise HTTPException(422, '请填写SKU')
    session.commit()
    data = source.fetch(sku)
    session.refresh(actor)
    authorize_member(session, actor, 'task.create')
    return source.public_metadata(session, sku, data)


@router.get('/requirement-draft')
def get(actor: CurrentMember, session: Database):
    return read.get(session, actor)


@router.put('/requirement-draft', dependencies=protected)
def save(body: SaveDraft, actor: CurrentMember, session: Database):
    return service.save(session, actor, body)


@router.delete('/requirement-draft', dependencies=protected)
def clear(body: VersionBody, actor: CurrentMember, session: Database):
    return service.clear(session, actor, body)


@router.post('/requirement-draft/source', dependencies=protected)
def select(body: SelectSource, actor: CurrentMember, session: Database):
    return select_source(session, actor, body)


@router.post('/requirement-draft/imports/{identifier}/retry', dependencies=protected)
def retry(identifier: UUID, actor: CurrentMember, session: Database):
    return service.modify_import(session, actor, identifier, retry=True)


@router.delete('/requirement-draft/imports/{identifier}', dependencies=protected)
def cancel(identifier: UUID, actor: CurrentMember, session: Database):
    return service.modify_import(session, actor, identifier)


@router.delete('/requirement-draft/materials/{identifier}', dependencies=protected)
def remove(identifier: UUID, actor: CurrentMember, session: Database):
    return service.remove_material(session, actor, identifier)
