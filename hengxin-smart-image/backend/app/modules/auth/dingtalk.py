"""DingTalk OAuth and enterprise-member mapping for Phase 12.2."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
LOGIN_STATE_TTL = timedelta(minutes=10)
CALLBACK_PATH = '/api/v1/auth/dingtalk/callback'
ALLOWED_RETURN_PATHS = (
    '/image-processing/wallpaper', '/image-processing/product', '/image-processing/text',
    '/tasks/index', '/templates/index', '/archive/index',
    '/management/usage', '/management/monitor', '/management/users',
    '/management/skills', '/management/settings',
)


class DingTalkProviderError(RuntimeError):
    """The provider could not complete an authorization request."""


class DingTalkEnterpriseMismatch(HTTPException):
    def __init__(self):
        super().__init__(403, '当前钉钉账号不属于目标企业')


class DingTalkAccountError(HTTPException):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(403, message)


@dataclass(frozen=True)
class DingTalkMember:
    provider_user_id: str
    name: str
    union_id: str | None
    department: str
    corp_id: str


def is_configured(settings: Settings | None = None) -> bool:
    value = settings or get_settings()
    return all((
        value.dingtalk_corp_id, value.dingtalk_client_id, value.dingtalk_agent_id,
        value.dingtalk_client_secret, value.dingtalk_callback_domain,
    ))


def public_config(settings: Settings | None = None) -> dict[str, Any]:
    value = settings or get_settings()
    return {
        'configured': is_configured(value),
        'corpId': value.dingtalk_corp_id if is_configured(value) else '',
        'clientId': value.dingtalk_client_id if is_configured(value) else '',
        'callbackPath': CALLBACK_PATH,
    }


def safe_return_path(value: str | None) -> str:
    if not value:
        return ALLOWED_RETURN_PATHS[0]
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.fragment or '\r' in value or '\n' in value:
        return ALLOWED_RETURN_PATHS[0]
    if parsed.path not in ALLOWED_RETURN_PATHS:
        return ALLOWED_RETURN_PATHS[0]
    return urlunsplit(('', '', parsed.path, parsed.query, ''))


def callback_url(settings: Settings | None = None) -> str:
    value = settings or get_settings()
    return value.dingtalk_callback_domain.rstrip('/') + CALLBACK_PATH


def configured_admin_user_ids(settings: Settings | None = None) -> frozenset[str]:
    value = settings or get_settings()
    raw_values = [value.dingtalk_admin_user_ids, value.dingtalk_admin_user_id]
    return frozenset(
        item.strip()
        for raw_value in raw_values
        for item in raw_value.split(',')
        if item.strip()
    )


def browser_authorize_url(state: str, settings: Settings | None = None,
                          redirect_uri: str | None = None) -> str:
    value = settings or get_settings()
    if not is_configured(value):
        raise DingTalkProviderError('DingTalk is not configured')
    query = urlencode({
        'redirect_uri': redirect_uri or callback_url(value),
        'client_id': value.dingtalk_client_id,
        'response_type': 'code',
        'scope': 'openid corpid',
        'state': state,
        'prompt': 'consent',
    })
    return 'https://login.dingtalk.com/oauth2/auth?' + query


def _request_json(url: str, method: str = 'GET', body: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None) -> dict[str, Any]:
    payload = json.dumps(body).encode('utf-8') if body is not None else None
    request = Request(url, data=payload, method=method, headers={
        'Accept': 'application/json',
        **({'Content-Type': 'application/json'} if body is not None else {}),
        **(headers or {}),
    })
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        status = getattr(error, 'code', '')
        logger.warning('DingTalk provider request failed method=%s path=%s status=%s',
                       method, urlsplit(url).path, status)
        raise DingTalkProviderError('DingTalk authorization service is unavailable') from error
    if not isinstance(result, dict):
        raise DingTalkProviderError('DingTalk returned an invalid response')
    return result


def exchange_auth_code(code: str, settings: Settings | None = None) -> DingTalkMember:
    value = settings or get_settings()
    if not is_configured(value) or not code.strip():
        raise DingTalkProviderError('DingTalk is not configured')
    token = _request_json(value.dingtalk_api_base_url.rstrip('/') + '/v1.0/oauth2/userAccessToken', 'POST', {
        'clientId': value.dingtalk_client_id,
        'clientSecret': value.dingtalk_client_secret,
        'code': code,
        'grantType': 'authorization_code',
    })
    access_token = token.get('accessToken') or token.get('access_token')
    if not isinstance(access_token, str) or not access_token:
        raise DingTalkProviderError('DingTalk did not return an access token')
    profile = _request_json(value.dingtalk_api_base_url.rstrip('/') + '/v1.0/contact/users/me', headers={
        'x-acs-dingtalk-access-token': access_token,
    })
    union_id = _first_string(profile, 'unionId', 'unionid')
    if not union_id:
        raise DingTalkProviderError('DingTalk did not return unionId')
    corp_id = _first_string(token, 'corpId', 'corp_id') or _first_string(profile, 'corpId', 'corp_id') or value.dingtalk_corp_id
    if corp_id != value.dingtalk_corp_id:
        raise DingTalkEnterpriseMismatch()
    app_token = _request_json(value.dingtalk_api_base_url.rstrip('/') + '/v1.0/oauth2/accessToken', 'POST', {
        'appKey': value.dingtalk_client_id, 'appSecret': value.dingtalk_client_secret,
    })
    app_access = _first_string(app_token, 'accessToken')
    if not app_access:
        raise DingTalkProviderError('DingTalk did not return application token')
    query = urlencode({'access_token': app_access})
    mapped = _request_json('https://oapi.dingtalk.com/topapi/user/getbyunionid?' + query,
                           'POST', {'unionid': union_id})
    result = mapped.get('result')
    if str(mapped.get('errcode')) != '0' or not isinstance(result, dict):
        raise DingTalkProviderError('Enterprise member mapping failed')
    provider_user_id = _first_string(result, 'userid')
    if not provider_user_id or str(result.get('contact_type', '0')) != '0':
        raise DingTalkEnterpriseMismatch()
    detail = _request_json('https://oapi.dingtalk.com/topapi/v2/user/get?' + query,
                           'POST', {'userid': provider_user_id})
    employee = detail.get('result')
    if str(detail.get('errcode')) != '0' or not isinstance(employee, dict):
        raise DingTalkProviderError('Enterprise member verification failed')
    if employee.get('userid') != provider_user_id or employee.get('unionid') != union_id:
        raise DingTalkEnterpriseMismatch()
    return DingTalkMember(
        provider_user_id=provider_user_id,
        name=_first_string(employee, 'name') or provider_user_id,
        union_id=union_id,
        department=_first_string(profile, 'department', 'departmentName') or '',
        corp_id=corp_id,
    )


def exchange_container_code(code: str, settings: Settings | None = None) -> DingTalkMember:
    value = settings or get_settings()
    if not is_configured(value) or not code.strip():
        raise DingTalkProviderError('DingTalk is not configured')
    app_token = _request_json(value.dingtalk_api_base_url.rstrip('/') + '/v1.0/oauth2/accessToken', 'POST', {
        'appKey': value.dingtalk_client_id, 'appSecret': value.dingtalk_client_secret,
    })
    app_access = _first_string(app_token, 'accessToken')
    if not app_access:
        raise DingTalkProviderError('DingTalk did not return application token')
    query = urlencode({'access_token': app_access})
    mapped = _request_json(
        'https://oapi.dingtalk.com/topapi/v2/user/getuserinfo?' + query,
        'POST', {'code': code.strip()},
    )
    result = mapped.get('result')
    if str(mapped.get('errcode')) != '0' or not isinstance(result, dict):
        logger.warning(
            'DingTalk getuserinfo failed errcode=%s', mapped.get('errcode'),
        )
        raise DingTalkProviderError('Enterprise member mapping failed')
    provider_user_id = _first_string(result, 'userid')
    union_id = _first_string(result, 'unionid')
    if not provider_user_id:
        raise DingTalkProviderError('DingTalk did not return userid')
    detail = _request_json(
        'https://oapi.dingtalk.com/topapi/v2/user/get?' + query,
        'POST', {'userid': provider_user_id},
    )
    employee = detail.get('result')
    if str(detail.get('errcode')) != '0' or not isinstance(employee, dict):
        logger.warning(
            'DingTalk user get failed errcode=%s', detail.get('errcode'),
        )
        raise DingTalkProviderError('Enterprise member verification failed')
    if employee.get('userid') != provider_user_id:
        raise DingTalkEnterpriseMismatch()
    if union_id and employee.get('unionid') not in (None, union_id):
        raise DingTalkEnterpriseMismatch()
    return DingTalkMember(
        provider_user_id=provider_user_id,
        name=_first_string(employee, 'name') or _first_string(result, 'name') or provider_user_id,
        union_id=_first_string(employee, 'unionid') or union_id,
        department='',
        corp_id=value.dingtalk_corp_id,
    )


def _first_string(values: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = values.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def create_login_state(session, return_path: str) -> str:
    from app.modules.auth.dingtalk_members import create_login_state as create
    return create(session, return_path)


def consume_login_state(session, state: str) -> str:
    from app.modules.auth.dingtalk_members import consume_login_state as consume
    return consume(session, state)


def authenticate_member(session, member: DingTalkMember):
    from app.modules.auth.dingtalk_members import authenticate_member as authenticate
    return authenticate(session, member, get_settings())


def __getattr__(name):
    # Preserve legacy callers without importing domestic ORM in the identity process.
    if name in ('AuthLoginStateRecord', 'UserIdentityRecord', '_hash_state'):
        from app.modules.auth import dingtalk_members
        return getattr(dingtalk_members, name)
    raise AttributeError(name)
