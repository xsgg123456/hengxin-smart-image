"""Only fixed publisher routes over a local, permission-protected Unix socket."""
import os
import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from .installed_tree import MAX_FILE

SOCKET_DEFAULT = '/run/hengxin-skill-publisher/publisher.sock'
MAX_JSON = 2 * 1024 * 1024


async def bounded_stream(request, maximum=MAX_FILE):
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > maximum:
            raise HTTPException(413, '请求超过允许的大小')
        yield chunk


async def parse_body(request, model):
    data = bytearray()
    async for chunk in bounded_stream(request, MAX_JSON):
        data.extend(chunk)
    try:
        return model.model_validate_json(data)
    except (ValidationError, ValueError):
        raise HTTPException(422, '文件夹清单或操作参数无效，请检查路径、数量、大小及校验值') from None


async def request(method, path, actor, *, body=None, content=None, params=None, key=None):
    transport = httpx.AsyncHTTPTransport(uds=os.environ.get('HX_SKILL_PUBLISH_SOCKET', SOCKET_DEFAULT))
    try:
        async with httpx.AsyncClient(transport=transport, timeout=180, trust_env=False) as client:
            response = await client.request(method, 'http://publisher' + path,
                headers={'X-Actor-Id': str(actor.id), **({'Idempotency-Key': key} if key else {})},
                json=body, content=content, params=params)
        if response.status_code >= 400:
            try:
                detail = response.json()['detail']
            except (ValueError, KeyError):
                detail = 'Skill 发布服务请求失败，可查询记录后重试'
            raise HTTPException(response.status_code, detail)
        return response.json()
    except httpx.HTTPError:
        raise HTTPException(503, 'Skill 发布服务暂不可用，上传记录已保存，可稍后重试') from None
