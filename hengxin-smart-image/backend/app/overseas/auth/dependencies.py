from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.browser_auth import require_identity_session
from app.db.session import get_session
from app.overseas.auth.models import Member, MemberRole, ROLES
from app.overseas.auth.sessions import SESSION_COOKIE, resolve_session


def member_roles(session: Session, member: Member) -> list[str]:
    roles = list(session.scalars(select(MemberRole.role).where(
        MemberRole.user_id == member.id, MemberRole.role.in_(ROLES),
    ).order_by(MemberRole.role)))
    if member.directory_state != 'enrolled' or member.status != 'active' or len(roles) != 1:
        raise HTTPException(403, '海外账号未授权或已停用')
    return roles


def get_current_member(
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    session: Session = Depends(get_session),
):
    record = resolve_session(session, token) if token else None
    if record is None:
        raise HTTPException(401, '请先登录海外业务')
    require_identity_session(record.identity_session_id)
    member = session.get(Member, record.user_id)
    if member is None:
        raise HTTPException(401, '海外登录身份无效')
    member_roles(session, member)
    member.identity_session_id = record.identity_session_id
    return member


CurrentMember = Annotated[Member, Depends(get_current_member)]
