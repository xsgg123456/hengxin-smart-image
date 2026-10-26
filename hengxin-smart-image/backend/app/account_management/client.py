"""Bounded management exchange with the current deployment's private socket."""
import socket
import time

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.execution.credential_broker_client import receive, send

MAX_REQUEST = 16 * 1024
MAX_RESPONSE = 128 * 1024
TIMEOUT = 8
UNAVAILABLE = 'Codex 账号管理服务暂不可用，请稍后重试'


def _exchange(path, payload):
    deadline = time.monotonic() + TIMEOUT
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(max(0.001, deadline - time.monotonic()))
        connection.connect(path)
        send(connection, payload, MAX_REQUEST, deadline)
        return receive(connection, MAX_RESPONSE, deadline)


async def request(action, actor, model, **fields):
    path = get_settings().codex_account_management_socket
    if not path:
        raise HTTPException(503, 'Codex 账号管理服务尚未配置，请联系管理员')
    payload = {'action': action, 'actor': {'id': str(actor.id), 'name': actor.name}, **fields}
    try:
        response = await run_in_threadpool(_exchange, path, payload)
        if set(response) == {'error'}:
            error = response['error']
            if (isinstance(error, dict) and type(error.get('status')) is int
                    and error['status'] in (400, 403, 404, 409, 503)
                    and isinstance(error.get('message'), str) and error['message']):
                raise HTTPException(error['status'], error['message'])
            raise ValueError('invalid management error')
        if set(response) != {'data'} or not isinstance(response['data'], dict):
            raise ValueError('invalid management response')
        return model.model_validate(response['data'])
    except HTTPException:
        raise
    except (OSError, ValueError, TypeError, AttributeError, ValidationError):
        # Socket paths, malformed payloads and credential contents never reach HTTP errors.
        raise HTTPException(503, UNAVAILABLE) from None
