from datetime import timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.models import utcnow
from .models import RetentionEntry

CACHE_AGE = timedelta(days=1)
HISTORY_AGE = timedelta(days=7)
PENDING = ('cache_pending', 'expire_pending')


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def entry(session, domain, resource_id):
    return session.scalar(select(RetentionEntry).where(
        RetentionEntry.domain == domain, RetentionEntry.resource_id == resource_id))


def guard(session, domain, resource_id, restart=False):
    """Caller holds the business parent lock; no independent lock-order inversion."""
    row = entry(session, domain, resource_id)
    if row and row.status in PENDING:
        raise HTTPException(409, '会话正在清理，请稍后重试')
    if row and row.status == 'expired':
        if not restart:
            raise HTTPException(409, '会话历史已清理，请基于成品开启新会话')
        row.status, row.expired_at = 'active', None
    return row


def touch(session, domain, resource_id, now=None):
    now = now or utcnow()
    row = entry(session, domain, resource_id)
    if row is None:
        row = RetentionEntry(domain=domain, resource_id=resource_id,
                             last_activity_at=now, next_cleanup_at=now + CACHE_AGE)
        session.add(row)
    else:
        if row.status in PENDING or row.status == 'expired':
            raise HTTPException(409, '会话已清理或正在清理，请刷新后重试')
        row.last_activity_at = max(aware(row.last_activity_at), aware(now))
        row.next_cleanup_at = row.last_activity_at + CACHE_AGE
        row.cache_cleared_at, row.error = None, None
    return row


def describe(session, domain, resource_id):
    row = entry(session, domain, resource_id)
    if not row:
        return None
    return {'status': row.status, 'lastActivityAt': aware(row.last_activity_at).isoformat(),
            'expiresAt': (aware(row.last_activity_at) + HISTORY_AGE).isoformat(),
            'cacheClearedAt': aware(row.cache_cleared_at).isoformat() if row.cache_cleared_at else None}


def due(row, now):
    if row.status in PENDING:
        return row.status
    if row.status == 'expired':
        return None
    if aware(row.last_activity_at) + HISTORY_AGE <= now:
        return 'expire_pending'
    if row.cache_cleared_at is None and aware(row.last_activity_at) + CACHE_AGE <= now:
        return 'cache_pending'
    return None
