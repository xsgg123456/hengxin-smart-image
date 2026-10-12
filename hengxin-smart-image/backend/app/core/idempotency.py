"""Shared request hashing and locking; callers supply their own business model."""
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select, text


def fingerprint_payload(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def lookup_request(session, model, user_id, operation, target, key, body_hash):
    if not key or not key.strip() or len(key) > 128:
        raise HTTPException(422, '必须提供1至128字符的 Idempotency-Key')
    if session.get_bind().dialect.name == 'postgresql':
        scope = f'{user_id}:{operation}:{target}:{key}'
        lock_id = int.from_bytes(hashlib.sha256(scope.encode()).digest()[:8], 'big', signed=True)
        session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_id})
    request = session.scalar(select(model).where(model.user_id == user_id,
        model.operation == operation, model.target == target, model.key == key))
    if request is not None and request.body_hash != body_hash:
        raise HTTPException(409, '同一幂等键不能提交不同内容')
    return request
