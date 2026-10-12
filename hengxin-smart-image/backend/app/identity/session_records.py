"""Shared session persistence; the caller supplies its own business model."""
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from app.identity.tokens import hash_token, is_expired, new_token, utcnow


def issue(session, model, user_id, ttl_seconds, now=None, expires_at=None, **fields):
    issued_at = now or utcnow()
    expiry = issued_at + timedelta(seconds=ttl_seconds)
    if expires_at is not None:
        if is_expired(expires_at, issued_at):
            raise HTTPException(401, '统一身份已过期')
        expiry = min(expiry, expires_at)
    token = new_token()
    session.add(model(user_id=user_id, token_hash=hash_token(token),
                      expires_at=expiry, last_seen_at=issued_at, **fields))
    session.flush()
    return token


def resolve(session, model, token, now=None):
    record = session.scalar(select(model).where(model.token_hash == hash_token(token)))
    if record is None or record.revoked_at is not None or is_expired(record.expires_at, now):
        return None
    return record


def revoke(session, model, token, now=None):
    record = session.scalar(select(model).where(model.token_hash == hash_token(token)))
    if record is None or record.revoked_at is not None:
        return False
    record.revoked_at = now or utcnow()
    return True
