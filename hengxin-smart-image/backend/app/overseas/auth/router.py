from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.browser_auth import TicketInput, browser_request, redeem_business_ticket, set_business_cookie
from app.db.session import get_session
from app.overseas.auth.dependencies import CurrentMember, member_roles
from app.overseas.auth.identity import bind_member
from app.overseas.auth.sessions import COOKIE_PATH, SESSION_COOKIE, issue_session, revoke_session

router = APIRouter(prefix='/api/overseas/v1/auth', tags=['overseas-auth'])


class OverseasUser(BaseModel):
    id: str
    name: str
    status: str
    roles: list[str]


def describe(session, member):
    return OverseasUser(id=str(member.id), name=member.name, status=member.status,
                        roles=member_roles(session, member))


@router.post('/identity/session', response_model=OverseasUser, dependencies=[Depends(browser_request)])
def exchange(body: TicketInput, response: Response,
             previous: str | None = Cookie(default=None, alias=SESSION_COOKIE),
             session: Session = Depends(get_session)):
    assertion = redeem_business_ticket(body.ticket)
    if previous:
        revoke_session(session, previous)
    member = bind_member(session, assertion['member'])
    try:
        result = describe(session, member)
    except HTTPException:
        session.commit()  # Register pending identity for later authorization, never a session.
        raise
    token = issue_session(session, member.id, assertion['identity_session_id'],
                          datetime.fromisoformat(assertion['expires_at']))
    session.commit()
    set_business_cookie(response, SESSION_COOKIE, token, COOKIE_PATH)
    return result


@router.get('/me', response_model=OverseasUser)
def me(member: CurrentMember, session: Session = Depends(get_session)):
    return describe(session, member)


@router.post('/logout', status_code=204, dependencies=[Depends(browser_request)])
def logout(response: Response, token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
           session: Session = Depends(get_session)):
    if token and revoke_session(session, token):
        session.commit()
    response.delete_cookie(SESSION_COOKIE, path=COOKIE_PATH)
