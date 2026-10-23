from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.browser_auth import TicketInput, browser_request, redeem_business_ticket, set_business_cookie
from app.db.session import get_session
from app.overseas.auth.dependencies import CurrentMember, member_roles
from app.overseas.auth.identity import bind_member
from app.overseas.auth.sessions import COOKIE_PATH, SESSION_COOKIE, issue_session, revoke_session
from app.overseas.permissions import capabilities, principal_for
from app.overseas.members.service import lock_permissions

router = APIRouter(prefix='/api/overseas/v1/auth', tags=['overseas-auth'])


class OverseasUser(BaseModel):
    id: str
    name: str
    status: str
    roles: list[str]
    capabilities: list[str]
    identitySessionId: str | None = None


def describe(session, member, identity_session_id=None):
    roles = member_roles(session, member)
    return OverseasUser(id=str(member.id), name=member.name, status=member.status,
                        roles=roles, capabilities=capabilities(principal_for(session, member).roles),
                        identitySessionId=identity_session_id)


@router.post('/identity/session', response_model=OverseasUser, dependencies=[Depends(browser_request)])
def exchange(body: TicketInput, response: Response,
             previous: str | None = Cookie(default=None, alias=SESSION_COOKIE),
             session: Session = Depends(get_session)):
    assertion = redeem_business_ticket(body.ticket)
    lock_permissions(session)
    if previous:
        revoke_session(session, previous)
    try:
        member = bind_member(session, assertion['member'])
        result = describe(session, member, assertion['identity_session_id'])
    except HTTPException:
        session.commit()  # Persist only revocation of the browser's previous business session.
        raise
    token = issue_session(session, member.id, assertion['identity_session_id'],
                          datetime.fromisoformat(assertion['expires_at']))
    session.commit()
    set_business_cookie(response, SESSION_COOKIE, token, COOKIE_PATH)
    return result


@router.get('/me', response_model=OverseasUser)
def me(member: CurrentMember, session: Session = Depends(get_session)):
    return describe(session, member, getattr(member, 'identity_session_id', None))


@router.post('/logout', status_code=204, dependencies=[Depends(browser_request)])
def logout(response: Response, token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
           session: Session = Depends(get_session)):
    if token and revoke_session(session, token):
        session.commit()
    response.delete_cookie(SESSION_COOKIE, path=COOKIE_PATH)
