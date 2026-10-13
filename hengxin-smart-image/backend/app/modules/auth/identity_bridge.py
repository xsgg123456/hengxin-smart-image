"""Exchange the neutral enterprise identity using domestic authorization rules."""
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

from app.contracts.business import User
from app.core.browser_auth import TicketInput, browser_request, redeem_business_ticket, set_business_cookie
from app.db.session import get_session
from app.modules.auth import dingtalk
from app.modules.auth.member_policy import lock_permissions
from app.modules.auth.sessions import SESSION_COOKIE, resolve_session, revoke_session

router = APIRouter(prefix='/api/v1/auth', tags=['auth'])


@router.post('/identity/session', response_model=User, dependencies=[Depends(browser_request)])
def exchange(body: TicketInput, response: Response,
             previous: str | None = Cookie(default=None, alias=SESSION_COOKIE),
             session: Session = Depends(get_session)):
    assertion = redeem_business_ticket(body.ticket)
    lock_permissions(session)
    if previous:
        revoke_session(session, previous)
    member = dingtalk.DingTalkMember(**assertion['member'])
    try:
        user, token = dingtalk.authenticate_member(session, member)
    except dingtalk.DingTalkAccountError:
        session.commit()
        raise
    record = resolve_session(session, token)
    record.identity_session_id = assertion['identity_session_id']
    identity_expiry = datetime.fromisoformat(assertion['expires_at'])
    local_expiry = record.expires_at
    if local_expiry.tzinfo is None:
        local_expiry = local_expiry.replace(tzinfo=timezone.utc)
    record.expires_at = min(local_expiry, identity_expiry)
    session.commit()
    set_business_cookie(response, SESSION_COOKIE, token, '/')
    return User(id=str(user.id), name=user.name, role=user.role, status=user.status,
                identitySessionId=record.identity_session_id)
