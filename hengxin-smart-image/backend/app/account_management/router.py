"""Same contract, deployment-selected identity and management permissions."""
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, Response
from sqlalchemy.orm import Session

from app.core.browser_auth import browser_request
from app.core.config import get_business_context
from app.db.session import get_session
from . import client
from .schemas import Account, ActivateInput, Authorization, Cancelled, Input, RemoveInput, StartInput


def administrator(request: Request, session: Session = Depends(get_session)):
    if get_business_context() == 'overseas':
        from app.overseas.auth.dependencies import get_current_member
        from app.overseas.auth.sessions import SESSION_COOKIE
        from app.overseas.permissions import authorize_member
        actor = get_current_member(request.cookies.get(SESSION_COOKIE), session)
        return authorize_member(session, actor, 'settings.manage')
    from app.modules.auth.dependencies import get_current_user, get_identity_id
    from app.modules.auth.sessions import SESSION_COOKIE
    from app.modules.auth.permissions import authorize
    identity = get_identity_id(request.cookies.get(SESSION_COOKIE))
    return authorize(get_current_user(identity, session), 'manage_system')


def private_response(request: Request, response: Response):
    response.headers['Cache-Control'] = 'private, no-store'
    if request.query_params:
        raise HTTPException(422, '请求参数不符合接口约定')


router = APIRouter(prefix='/management/codex-auth', tags=['codex-account'],
                   dependencies=[Depends(private_response)])
Admin = Annotated[object, Depends(administrator)]
Identifier = Annotated[str, Path(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')]
Empty = Annotated[Input | None, Body()]
WRITE = [Depends(browser_request)]


@router.get('', response_model=Account)
async def status(actor: Admin):
    return await client.request('status', actor, Account)


@router.post('/check', response_model=Account, dependencies=WRITE)
async def check(actor: Admin, body: Empty = None):
    return await client.request('check', actor, Account)


@router.post('/authorizations', response_model=Authorization, dependencies=WRITE)
async def start(body: StartInput, actor: Admin):
    return await client.request('start', actor, Authorization, **body.model_dump())


@router.get('/authorizations/{identifier}', response_model=Authorization)
async def poll(identifier: Identifier, actor: Admin):
    return await client.request('poll', actor, Authorization, id=identifier)


@router.post('/authorizations/{identifier}/retry', response_model=Authorization, dependencies=WRITE)
async def retry(identifier: Identifier, actor: Admin, body: Empty = None):
    return await client.request('retry', actor, Authorization, id=identifier)


@router.post('/authorizations/{identifier}/activate', response_model=Account, dependencies=WRITE)
async def activate(identifier: Identifier, body: ActivateInput, actor: Admin):
    return await client.request('activate', actor, Account, id=identifier, **body.model_dump())


@router.delete('/authorizations/{identifier}', response_model=Cancelled, dependencies=WRITE)
async def cancel(identifier: Identifier, actor: Admin, body: Empty = None):
    return await client.request('cancel', actor, Cancelled, id=identifier)


@router.delete('', response_model=Account, dependencies=WRITE)
async def remove(body: RemoveInput, actor: Admin):
    return await client.request('remove', actor, Account, **body.model_dump())
