from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.modules.auth.sessions import SESSION_COOKIE, resolve_session
from app.resource_models import UserRecord


def get_identity_id(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    """Resolve only the server-issued session cookie, with an explicit dev fallback."""
    if session_token:
        return session_token
    settings = get_settings()
    if settings.app_env == 'production' or not settings.enable_dev_identity:
        raise HTTPException(401, '请先登录')
    return settings.dev_user_id


def get_current_user(identity_id=Depends(get_identity_id), session: Session = Depends(get_session)):
    if isinstance(identity_id, str):
        auth_session = resolve_session(session, identity_id)
        if auth_session is None:
            raise HTTPException(401, '登录身份无效或已过期')
        identity_id = auth_session.user_id
    user = session.get(UserRecord, identity_id)
    if user is None:
        raise HTTPException(401, '登录身份无效')
    if get_settings().app_env == 'production' and user.identity_source == 'development':
        raise HTTPException(401, '开发身份不可用于生产')
    if user.status != 'active' or user.role not in (
        'super_admin', 'design_manager', 'designer', 'operator',
    ):
        raise HTTPException(403, '账号未授权或已停用')
    return user


CurrentUser = Annotated[UserRecord, Depends(get_current_user)]
