"""Issue and resolve server-side browser sessions."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import utcnow
from app.modules.auth.models import AuthSessionRecord

SESSION_COOKIE = 'hx_session'


def hash_session_token(token: str) -> str:
    return sha256(token.encode('utf-8')).hexdigest()


def issue_session(session: Session, user_id: UUID, now: datetime | None = None) -> str:
    issued_at = now or utcnow()
    token = secrets.token_urlsafe(48)
    record = AuthSessionRecord(
        user_id=user_id,
        token_hash=hash_session_token(token),
        expires_at=issued_at + timedelta(seconds=get_settings().auth_session_ttl_seconds),
        last_seen_at=issued_at,
    )
    session.add(record)
    session.flush()
    return token


def resolve_session(session: Session, token: str, now: datetime | None = None) -> AuthSessionRecord | None:
    record = session.scalar(select(AuthSessionRecord).where(
        AuthSessionRecord.token_hash == hash_session_token(token),
    ))
    current = now or datetime.now(timezone.utc)
    expires_at = record.expires_at if record else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if record is None or record.revoked_at is not None or expires_at <= current:
        return None
    return record


def revoke_session(session: Session, token: str, now: datetime | None = None) -> bool:
    record = session.scalar(select(AuthSessionRecord).where(
        AuthSessionRecord.token_hash == hash_session_token(token),
    ))
    if record is None or record.revoked_at is not None:
        return False
    record.revoked_at = now or utcnow()
    return True
