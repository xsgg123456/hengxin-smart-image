from secrets import compare_digest
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.contracts import business as b
from app.db.session import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.member_policy import lock_permissions
from app.modules.auth import dingtalk
from app.modules.auth.sessions import SESSION_COOKIE, revoke_session

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
    redirect: str = Query('/api-image-edits/create'),
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
    previous: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    return_path = '/api-image-edits/create'
    if not isinstance(login_state, str) or not compare_digest(state.encode(), login_state.encode()):
        return _callback_response(return_path, 'denied')
    try:
        return_path = dingtalk.consume_login_state(session, state)
        # 消费记录单独提交，后续远端调用或身份校验失败也不能恢复此 state。
        session.commit()
        member = dingtalk.exchange_auth_code(code or authCode or '')
        lock_permissions(session)
        if previous:
            revoke_session(session, previous)
        user, token = dingtalk.authenticate_member(session, member)
        session.commit()
    except dingtalk.DingTalkAccountError as error:
        # 未加入不建档；仅保留换号时对旧业务会话的撤销。
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
    previous: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    if not dingtalk.is_configured():
        raise HTTPException(503, '钉钉认证尚未配置')
    try:
        member = dingtalk.exchange_container_code(body.code)
        lock_permissions(session)
        if previous:
            revoke_session(session, previous)
        user, token = dingtalk.authenticate_member(session, member)
        session.commit()
    except dingtalk.DingTalkProviderError as error:
        session.rollback()
        raise HTTPException(503, '钉钉认证服务暂不可用，请稍后重试') from error
    except dingtalk.DingTalkEnterpriseMismatch:
        session.rollback()
        raise
    except dingtalk.DingTalkAccountError:
        # 未加入不建档；保留旧业务会话撤销。
        session.commit()
        raise
    except Exception:
        session.rollback()
        raise
    _set_session_cookie(response, token)
    return b.User(id=str(user.id), name=user.name, role=user.role, status=user.status)


@router.get('/auth/me', response_model=b.User)
def me(user: CurrentUser):
    return b.User(id=str(user.id), name=user.name, role=user.role, status=user.status,
                  identitySessionId=getattr(user, 'identity_session_id', None))


@router.post('/auth/logout', status_code=204)
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    session: Session = Depends(get_session),
):
    if session_token and revoke_session(session, session_token):
        session.commit()
    response.delete_cookie(SESSION_COOKIE, path='/')
