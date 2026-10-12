"""Business-neutral browser exchange and identity checks."""
from typing import Annotated

from fastapi import Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.identity.client import check_identity, redeem_ticket


class TicketInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ticket: str = Field(min_length=1, max_length=512)


def browser_request(request: Request, x_hx_request: Annotated[str | None, Header()] = None):
    if x_hx_request != '1':
        raise HTTPException(403, '请求来源无效')
    origin = request.headers.get('origin')
    if origin and origin != get_settings().identity_public_origin.rstrip('/'):
        raise HTTPException(403, '请求来源无效')


def redeem_business_ticket(ticket: str):
    settings = get_settings()
    if not settings.identity_service_url or not settings.identity_service_key:
        raise HTTPException(503, '统一身份服务尚未配置')
    return redeem_ticket(settings.identity_service_url, settings.identity_service_key, ticket)


def require_identity_session(identity_session_id: str | None):
    if identity_session_id is None:
        return  # Legacy domestic sessions have no unified identity binding.
    settings = get_settings()
    if not settings.identity_service_url or not settings.identity_service_key:
        raise HTTPException(503, '统一身份服务尚未配置')
    if not check_identity(settings.identity_service_url, settings.identity_service_key, identity_session_id):
        raise HTTPException(401, '企业身份已退出或过期，请重新登录')


def set_business_cookie(response: Response, name: str, token: str, path: str):
    settings = get_settings()
    response.set_cookie(name, token, httponly=True, samesite='lax', path=path,
                        secure=settings.app_env == 'production' or settings.identity_public_origin.startswith('https://'),
                        max_age=settings.auth_session_ttl_seconds)
