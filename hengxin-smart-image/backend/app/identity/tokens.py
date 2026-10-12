"""Business-neutral cryptographic token and expiry primitives."""
from datetime import datetime, timezone
from hashlib import sha256
from secrets import token_urlsafe


def new_token() -> str:
    return token_urlsafe(48)


def hash_token(token: str) -> str:
    return sha256(token.encode('utf-8')).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_expired(expires_at: datetime, now: datetime | None = None) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= (now or utcnow())
