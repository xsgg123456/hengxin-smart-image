"""Domestic persistence and permission mapping for the shared DingTalk provider."""
from datetime import datetime, timezone
from hashlib import sha256
from secrets import token_urlsafe
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import utcnow
from app.modules.auth.models import AuthLoginStateRecord, UserIdentityRecord
from app.modules.auth.sessions import issue_session
from app.resource_models import UserRecord
from app.modules.auth.dingtalk import (DingTalkMember, DingTalkAccountError, LOGIN_STATE_TTL,
                                      safe_return_path, configured_admin_user_ids)

def _hash_state(state: str) -> str:
    return sha256(state.encode('utf-8')).hexdigest()


def create_login_state(session: Session, return_path: str) -> str:
    state = token_urlsafe(32)
    session.add(AuthLoginStateRecord(
        state_hash=_hash_state(state), return_path=safe_return_path(return_path),
        expires_at=utcnow() + LOGIN_STATE_TTL,
    ))
    session.flush()
    return state


def consume_login_state(session: Session, state: str) -> str:
    record = session.scalar(select(AuthLoginStateRecord).where(
        AuthLoginStateRecord.state_hash == _hash_state(state),
    ).with_for_update())
    current = datetime.now(timezone.utc)
    expires_at = record.expires_at if record else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if record is None or record.consumed_at is not None or expires_at <= current:
        raise HTTPException(400, '登录状态无效或已过期')
    record.consumed_at = utcnow()
    return safe_return_path(record.return_path)


def authenticate_member(session: Session, member: DingTalkMember, settings) -> tuple[UserRecord, str]:
    identity = session.scalar(select(UserIdentityRecord).where(
        UserIdentityRecord.provider == 'dingtalk',
        UserIdentityRecord.corp_id == member.corp_id,
        UserIdentityRecord.provider_user_id == member.provider_user_id,
    ))
    if identity is None:
        user = UserRecord(
            name=member.name, role=None, status='pending', identity_source='dingtalk',
        )
        if member.provider_user_id in configured_admin_user_ids(settings):
            user.role, user.status = 'super_admin', 'active'
        session.add(user)
        session.flush()
        session.add(UserIdentityRecord(
            user_id=user.id, provider='dingtalk', corp_id=member.corp_id,
            provider_user_id=member.provider_user_id, union_id=member.union_id,
            department=member.department,
        ))
    else:
        user = session.get(UserRecord, identity.user_id)
        if user is None:
            raise HTTPException(401, '登录身份无效')
        user.name = member.name
        identity.union_id = member.union_id
        identity.department = member.department
    if user.status == 'disabled':
        raise DingTalkAccountError('ACCOUNT_DISABLED', '账号已禁用，请联系超级管理员')
    if user.status != 'active' or user.role not in ('super_admin', 'design_manager', 'designer', 'operator'):
        raise DingTalkAccountError('AUTH_PENDING', '账号待授权，请联系超级管理员分配角色')
    return user, issue_session(session, user.id)
