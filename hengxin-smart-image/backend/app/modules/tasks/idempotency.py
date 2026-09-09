import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select, text
from .models import TaskRequest
from app.contracts.business import Accepted


def fingerprint(body):
    return hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode()).hexdigest()


def replay(session, user_id, operation, target, key, body_hash):
    if not key or not key.strip() or len(key) > 128:
        raise HTTPException(422, '必须提供1至128字符的 Idempotency-Key')
    if session.bind.dialect.name == 'postgresql':
        scope = f'{user_id}:{operation}:{target}:{key}'
        lock_id = int.from_bytes(hashlib.sha256(scope.encode()).digest()[:8], 'big', signed=True)
        session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_id})
    request = session.scalar(select(TaskRequest).where(TaskRequest.user_id == user_id,
        TaskRequest.operation == operation, TaskRequest.target == target, TaskRequest.key == key))
    if request:
        if request.body_hash != body_hash:
            raise HTTPException(409, '同一幂等键不能提交不同内容')
        return Accepted(taskId=str(request.task_id), roundId=str(request.round_id), state='排队中')
    return None
