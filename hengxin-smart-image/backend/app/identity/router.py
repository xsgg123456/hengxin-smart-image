"""Public identity endpoints and service-key authenticated internal endpoints."""
from secrets import compare_digest
from typing import Literal
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from app.modules.auth import dingtalk

PATH = '/api/identity/v1'
COOKIE = 'hx_identity'
STATE_COOKIE = 'hx_identity_state'
router = APIRouter()


class CodeInput(BaseModel):
    code: str = Field(min_length=1, max_length=2048)


class TicketInput(BaseModel):
    ticket: str = Field(min_length=1, max_length=512)


class BusinessInput(BaseModel):
    business: Literal['domestic', 'overseas']


class CheckInput(BaseModel):
    identity_session_id: str = Field(min_length=1, max_length=512)


def same_origin(request: Request):
    settings = request.app.state.settings
    if request.headers.get('X-HX-Request') != '1':
        raise HTTPException(403, '请求来源验证失败')
    origin = request.headers.get('origin')
    if origin and origin != settings.public_origin.rstrip('/'):
        raise HTTPException(403, '请求来源验证失败')


def service_business(request: Request):
    key = request.headers.get('X-HX-Service-Key', '')
    settings = request.app.state.settings
    # Evaluate both comparisons regardless of which business matches.
    matches = [compare_digest(key.encode(), value.encode()) for value in
               (settings.domestic_service_key, settings.overseas_service_key)]
    if matches[0]:
        return 'domestic'
    if matches[1]:
        return 'overseas'
    raise HTTPException(401, '服务身份无效')


def set_cookie(response, request, name, token, max_age):
    response.set_cookie(name, token, httponly=True, samesite='lax', path=PATH,
                        secure=urlsplit(request.app.state.settings.public_origin).scheme == 'https',
                        max_age=max_age)


def login(request, response, member):
    settings, store = request.app.state.settings, request.app.state.store
    if member.corp_id != settings.dingtalk_corp_id:
        raise dingtalk.DingTalkEnterpriseMismatch()
    store.revoke(request.cookies.get(COOKIE))
    token = store.create(member)
    set_cookie(response, request, COOKIE, token, settings.session_ttl_seconds)


@router.get(PATH + '/config')
def config(request: Request):
    value = dingtalk.public_config(request.app.state.settings)
    return {key: value[key] for key in ('configured', 'corpId', 'clientId')}


@router.get(PATH + '/me')
def me(request: Request):
    record = request.app.state.store.resolve(request.cookies.get(COOKIE))
    return {'name': record['member']['name']}


@router.get(PATH + '/dingtalk/authorize')
def authorize(request: Request):
    settings = request.app.state.settings
    if not dingtalk.is_configured(settings):
        raise HTTPException(503, '钉钉认证尚未配置')
    state = request.app.state.store.state()
    url = dingtalk.browser_authorize_url(
        state, settings, settings.public_origin.rstrip('/') + PATH + '/dingtalk/callback')
    response = RedirectResponse(url, status_code=303)
    set_cookie(response, request, STATE_COOKIE, state, 600)
    return response


@router.get(PATH + '/dingtalk/callback')
def callback(request: Request, state: str = '', code: str = '', authCode: str = ''):
    cookie = request.cookies.get(STATE_COOKIE, '')
    if not state or len(state) > 512 or not cookie or not compare_digest(state.encode(), cookie.encode()):
        raise HTTPException(400, '登录状态无效或已过期')
    if not request.app.state.store.consume_state(state):
        raise HTTPException(400, '登录状态无效或已过期')
    origin = request.app.state.settings.public_origin.rstrip('/')
    response = RedirectResponse(origin + '/#/auth/business', status_code=303)
    response.delete_cookie(STATE_COOKIE, path=PATH)
    try:
        member = dingtalk.exchange_auth_code(code or authCode, request.app.state.settings)
        login(request, response, member)
    except (dingtalk.DingTalkProviderError, dingtalk.DingTalkEnterpriseMismatch):
        response = RedirectResponse(origin + '/#/auth/login?auth=provider_error', status_code=303)
        response.delete_cookie(STATE_COOKIE, path=PATH)
    return response


@router.post(PATH + '/dingtalk/container', dependencies=[Depends(same_origin)])
def container(body: CodeInput, request: Request, response: Response):
    try:
        member = dingtalk.exchange_container_code(body.code, request.app.state.settings)
    except dingtalk.DingTalkProviderError as error:
        raise HTTPException(503, '钉钉认证暂不可用') from error
    login(request, response, member)
    return {'name': member.name}


@router.post(PATH + '/tickets', dependencies=[Depends(same_origin)])
def tickets(body: BusinessInput, request: Request):
    store = request.app.state.store
    record = store.resolve(request.cookies.get(COOKIE))
    return {'ticket': store.ticket(record, body.business)}


@router.post(PATH + '/logout', status_code=204, dependencies=[Depends(same_origin)])
def logout(request: Request):
    request.app.state.store.revoke(request.cookies.get(COOKIE))
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, path=PATH)
    return response


@router.post('/internal/redeem')
def redeem(body: TicketInput, request: Request, business=Depends(service_business)):
    return request.app.state.store.redeem(body.ticket, business)


@router.post('/internal/check')
def check(body: CheckInput, request: Request, _=Depends(service_business)):
    return {'active': request.app.state.store.by_id(body.identity_session_id) is not None}
