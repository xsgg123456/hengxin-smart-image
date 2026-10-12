"""Business-to-identity API client with explicit configuration and fail-closed errors."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from fastapi import HTTPException
from pydantic import ValidationError
from app.identity.schemas import IdentityGrant


def _post(service_url: str, service_key: str, path: str, body: dict) -> dict:
    if not service_url or not service_key:
        raise HTTPException(503, '统一身份服务尚未配置')
    request = Request(service_url.rstrip('/') + '/internal/' + path,
                      data=json.dumps(body).encode(), method='POST', headers={
                          'Content-Type': 'application/json', 'X-HX-Service-Key': service_key})
    try:
        with urlopen(request, timeout=3) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict):
            raise ValueError('invalid identity response')
        return result
    except HTTPError as error:
        if error.code == 401:
            raise HTTPException(401, '统一身份或凭据已失效') from error
        raise HTTPException(503, '统一身份服务暂不可用') from error
    except (URLError, OSError, TimeoutError, ValueError) as error:
        raise HTTPException(503, '统一身份服务暂不可用') from error


def redeem_ticket(service_url: str, service_key: str, ticket: str) -> dict:
    result = _post(service_url, service_key, 'redeem', {'ticket': ticket})
    try:
        return IdentityGrant.model_validate(result).model_dump(mode='json')
    except ValidationError as error:
        raise HTTPException(503, '统一身份服务返回无效凭据') from error


def check_identity(service_url: str, service_key: str, identity_session_id: str) -> bool:
    result = _post(service_url, service_key, 'check', {'identity_session_id': identity_session_id})
    if not isinstance(result.get('active'), bool):
        raise HTTPException(503, '统一身份服务返回无效状态')
    return result['active']
