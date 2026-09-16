from typing import Annotated
from secrets import compare_digest
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.contracts import business as b
from app.contracts import management as m
from app.db.session import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth import dingtalk
from app.modules.auth.models import AuthSessionRecord, RoleAssignmentRecord, UserIdentityRecord
from app.modules.auth.permissions import require_permission
from app.modules.auth.sessions import SESSION_COOKIE, revoke_session
from app.resource_models import UserRecord

router = APIRouter(tags=['auth'])
LOGIN_STATE_COOKIE = 'hx_dingtalk_login_state'


def _frontend_redirect(path: str, error: str | None = None):
    settings = dingtalk.get_settings()
    safe_path = dingtalk.safe_return_path(path)
    if error:
        query = urlencode({'auth': error, 'redirect': safe_path})
        return f'{settings.dingtalk_callback_domain.rstrip("/")}/#/auth/login?{query}'
    return f'{settings.dingtalk_callback_domain.rstrip("/")}#{safe_path}'


def _set_session_cookie(response: Response, token: str):
    secure = urlsplit(dingtalk.get_settings().dingtalk_callback_domain).scheme == 'https'
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, secure=secure,
        samesite='lax', max_age=dingtalk.get_settings().auth_session_ttl_seconds, path='/',
    )


@router.get('/auth/dingtalk/config', response_model=b.DingTalkAuthConfig)
def dingtalk_config():
    return dingtalk.public_config()


@router.get('/auth/dingtalk/authorize')
def dingtalk_authorize(
    redirect: str = Query('/image-processing/wallpaper'),
    session: Session = Depends(get_session),
):
    settings = dingtalk.get_settings()
    if not dingtalk.is_configured(settings):
        raise HTTPException(503, '钉钉认证尚未配置')
    state = dingtalk.create_login_state(session, redirect)
    session.commit()
    response = RedirectResponse(dingtalk.browser_authorize_url(state, settings), status_code=303)
    response.set_cookie(LOGIN_STATE_COOKIE, state, httponly=True,
                        secure=urlsplit(settings.dingtalk_callback_domain).scheme == 'https',
                        samesite='lax', max_age=600, path='/api/v1/auth/dingtalk')
    return response


def _callback_response(path: str, error: str | None = None):
    response = RedirectResponse(_frontend_redirect(path, error), status_code=303)
    response.delete_cookie(LOGIN_STATE_COOKIE, path='/api/v1/auth/dingtalk')
    return response


@router.get('/auth/dingtalk/callback')
def dingtalk_callback(
    state: str = Query(min_length=1, max_length=512),
    code: str | None = Query(default=None),
    authCode: str | None = Query(default=None),
    login_state: str | None = Cookie(default=None, alias=LOGIN_STATE_COOKIE),
    session: Session = Depends(get_session),
):
    return_path = '/image-processing/wallpaper'
    if not isinstance(login_state, str) or not compare_digest(state.encode(), login_state.encode()):
        return _callback_response(return_path, 'denied')
    try:
        return_path = dingtalk.consume_login_state(session, state)
        # 消费记录单独提交，后续远端调用或身份校验失败也不能恢复此 state。
        session.commit()
        member = dingtalk.exchange_auth_code(code or authCode or '')
        user, token = dingtalk.authenticate_member(session, member)
        session.commit()
    except dingtalk.DingTalkAccountError as error:
        # 保留首次登录的待授权成员映射，方便超级管理员后续分配角色。
        session.commit()
        return _callback_response(return_path, error.code)
    except dingtalk.DingTalkEnterpriseMismatch:
        session.rollback()
        return _callback_response(return_path, 'enterprise-mismatch')
    except dingtalk.DingTalkProviderError:
        session.rollback()
        return _callback_response(return_path, 'unavailable')
    except HTTPException as error:
        session.rollback()
        return _callback_response(return_path, 'denied')
    response = _callback_response(return_path)
    _set_session_cookie(response, token)
    return response


@router.post('/auth/dingtalk/container', response_model=b.User)
def dingtalk_container_login(
    body: b.DingTalkCodeInput,
    response: Response,
    session: Session = Depends(get_session),
):
    if not dingtalk.is_configured():
        raise HTTPException(503, '钉钉认证尚未配置')
    try:
        member = dingtalk.exchange_auth_code(body.code)
        user, token = dingtalk.authenticate_member(session, member)
        session.commit()
    except dingtalk.DingTalkProviderError as error:
        session.rollback()
        raise HTTPException(503, '钉钉认证服务暂不可用，请稍后重试') from error
    except dingtalk.DingTalkEnterpriseMismatch:
        session.rollback()
        raise
    except dingtalk.DingTalkAccountError:
        # 待授权成员需要落库，但永远不签发会话。
        session.commit()
        raise
    except Exception:
        session.rollback()
        raise
    _set_session_cookie(response, token)
    return b.User(id=str(user.id), name=user.name, role=user.role, status=user.status)


@router.get('/auth/me', response_model=b.User)
def me(user: CurrentUser):
    return b.User(id=str(user.id), name=user.name, role=user.role, status=user.status)


@router.post('/auth/logout', status_code=204)
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    session: Session = Depends(get_session),
):
    if session_token and revoke_session(session, session_token):
        session.commit()
    response.delete_cookie(SESSION_COOKIE, path='/')


def _department_expression():
    return select(UserIdentityRecord.department).where(
        UserIdentityRecord.user_id == UserRecord.id,
    ).order_by(UserIdentityRecord.created_at.desc()).limit(1).scalar_subquery()


def _last_login_expression():
    return select(func.max(AuthSessionRecord.created_at)).where(
        AuthSessionRecord.user_id == UserRecord.id,
    ).scalar_subquery()


def _user_filters(query: m.UserQuery):
    filters = []
    if query.status:
        filters.append(UserRecord.status == query.status)
    if query.role:
        filters.append(UserRecord.role == query.role)
    if query.search:
        pattern = f'%{query.search}%'
        department_match = select(UserIdentityRecord.id).where(
            UserIdentityRecord.user_id == UserRecord.id,
            UserIdentityRecord.department.ilike(pattern),
        ).exists()
        filters.append(or_(UserRecord.name.ilike(pattern), department_match))
    return filters


def _managed_user(user: UserRecord, department: str | None, last_login_at):
    return m.ManagedUser(
        id=str(user.id), name=user.name, role=user.role, status=user.status,
        department=department or '',
        lastLoginAt=last_login_at.isoformat() if last_login_at else None,
    )


@router.get('/management/users', response_model=b.PageResult[m.ManagedUser], tags=['management'])
def list_users(
    query: Annotated[m.UserQuery, Query()],
    _: Annotated[UserRecord, Depends(require_permission('manage_system'))],
    session: Session = Depends(get_session),
):
    filters = _user_filters(query)
    total = session.scalar(select(func.count()).select_from(UserRecord).where(*filters)) or 0
    rows = session.execute(
        select(UserRecord, _department_expression(), _last_login_expression())
        .where(*filters)
        .order_by(UserRecord.created_at.desc(), UserRecord.id)
        .offset((query.page - 1) * query.pageSize)
        .limit(query.pageSize),
    ).all()
    return b.PageResult[m.ManagedUser](
        items=[_managed_user(user, department, last_login_at) for user, department, last_login_at in rows],
        page=query.page, pageSize=query.pageSize, total=total,
    )


@router.put('/management/users/{user_id}', response_model=m.ManagedUser, tags=['management'])
def update_user(
    user_id: str,
    body: m.UserInput,
    actor: Annotated[UserRecord, Depends(require_permission('manage_system'))],
    session: Session = Depends(get_session),
):
    try:
        target_id = UUID(user_id)
    except ValueError as error:
        raise HTTPException(422, '成员 ID 无效') from error
    if body.id != user_id:
        raise HTTPException(422, '请求成员 ID 与路径不一致')
    target = session.get(UserRecord, target_id)
    if target is None:
        raise HTTPException(404, '成员不存在')
    if body.status == 'active' and body.role is None:
        raise HTTPException(422, '启用账号前必须分配业务角色')
    removing_last_admin = (
        target.status == 'active' and target.role == 'super_admin'
        and (body.status != 'active' or body.role != 'super_admin')
    )
    if removing_last_admin:
        active_admins = session.scalar(select(func.count()).select_from(UserRecord).where(
            UserRecord.status == 'active', UserRecord.role == 'super_admin',
        )) or 0
        if active_admins <= 1:
            raise HTTPException(409, '系统至少需要一名启用中的超级管理员')
    target.role, target.status = body.role, body.status
    assignment = session.scalar(select(RoleAssignmentRecord).where(
        RoleAssignmentRecord.user_id == target.id,
    ))
    if body.role is None:
        if assignment is not None:
            session.delete(assignment)
    elif assignment is None:
        session.add(RoleAssignmentRecord(user_id=target.id, role=body.role, assigned_by=actor.id))
    else:
        assignment.role, assignment.assigned_by = body.role, actor.id
    session.commit()
    department = session.scalar(select(UserIdentityRecord.department).where(
        UserIdentityRecord.user_id == target.id,
    ).order_by(UserIdentityRecord.created_at.desc()).limit(1))
    last_login_at = session.scalar(select(func.max(AuthSessionRecord.created_at)).where(
        AuthSessionRecord.user_id == target.id,
    ))
    return _managed_user(target, department, last_login_at)
