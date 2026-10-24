"""Short-lived metadata-only requests to the native execution filesystem owner."""
import json
import logging
import time
from types import SimpleNamespace
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.core.config import get_settings

PREFIX = 'overseas:studio:recovery:'
QUEUE = PREFIX + 'pending'
TTL = 30
WAIT_SECONDS = 25
MAX_PENDING = 32
UNAVAILABLE = '文件取回通道暂不可用或等待超时，请刷新后重试；已保存文件会保留'
ENQUEUE = """
if redis.call('LLEN', KEYS[1]) >= tonumber(ARGV[3]) then return 0 end
redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[4])
redis.call('RPUSH', KEYS[1], ARGV[1])
redis.call('EXPIRE', KEYS[1], ARGV[4])
return 1
"""


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=128)


class NativeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    operation: Literal['available', 'receive']
    actor_id: UUID
    task_id: UUID
    conversation_id: UUID
    expires_at: float = Field(allow_inf_nan=False)
    files: list[Selection] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def selection_matches_operation(self):
        if bool(self.files) != (self.operation == 'receive'):
            raise ValueError('Invalid recovery selection')
        return self


def connection():
    return Redis.from_url(get_settings().redis_url, decode_responses=True,
        socket_connect_timeout=1, socket_timeout=1, retry=Retry(NoBackoff(), 0))


def request(operation, actor_id, task_id, conversation_id, files=()):
    """No DB transaction or filesystem access is retained while waiting."""
    message = NativeRequest(id=uuid4(), operation=operation, actor_id=actor_id,
        task_id=task_id, conversation_id=conversation_id,
        expires_at=time.time() + WAIT_SECONDS,
        files=[item.model_dump() for item in files])
    request_key, response_key = PREFIX + 'request:' + str(message.id), PREFIX + 'response:' + str(message.id)
    try:
        with connection() as client:
            if not client.eval(ENQUEUE, 2, QUEUE, request_key, str(message.id),
                               message.model_dump_json(), MAX_PENDING, TTL):
                raise HTTPException(503, UNAVAILABLE)
            deadline = time.monotonic() + WAIT_SECONDS
            while time.monotonic() < deadline:
                raw = client.get(response_key)
                if raw is not None:
                    client.delete(response_key)
                    response = json.loads(raw)
                    if response['status'] != 200:
                        raise HTTPException(response['status'], response['detail'])
                    return response['result']
                time.sleep(0.1)
            # A consumer that already started may finish; retries use existing dedupe.
            client.delete(request_key)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, UNAVAILABLE) from None
    raise HTTPException(503, UNAVAILABLE)


def handle_native(factory, message, store=None):
    """Validate again at the native boundary, then use the original receipt code."""
    from . import recovery_files
    message = NativeRequest.model_validate(message)
    if message.expires_at <= time.time():
        raise HTTPException(503, UNAVAILABLE)
    if message.operation == 'available':
        with factory.begin() as session:
            return recovery_files.available(session, SimpleNamespace(id=message.actor_id),
                message.task_id, message.conversation_id)
    if store is None:
        from app.storage.minio_store import get_store
        store = get_store()
    return recovery_files.recover(factory, message.actor_id, message.task_id,
        message.conversation_id, message.files, store)


def consume_once(factory):
    """At most one request per maintenance pass; broken requests never stop outbox."""
    try:
        with connection() as client:
            identity = client.lpop(QUEUE)
            if identity is None:
                return False
            identity = str(UUID(identity))
            key = PREFIX + 'request:' + identity
            raw = client.get(key)
            client.delete(key)
            if raw is None:
                return False
            message = NativeRequest.model_validate_json(raw)
            if str(message.id) != identity or message.expires_at <= time.time():
                return False
            try:
                response = dict(status=200, result=handle_native(factory, message))
            except HTTPException as exc:
                response = dict(status=exc.status_code, detail=exc.detail)
            except Exception:
                response = dict(status=503, detail=UNAVAILABLE)
            client.set(PREFIX + 'response:' + identity, json.dumps(response), ex=TTL)
            return True
    except Exception:
        logging.warning('Native file recovery unavailable; refresh to retry')
        return False
