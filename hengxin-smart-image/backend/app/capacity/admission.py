"""Lock order: existing channel/task locks -> capacity gate; never the reverse."""
from datetime import timezone

from sqlalchemy import func, select

from app.models import utcnow
from .models import CapacityGate, CapacityReservation

WAITING = '等待存储容量，尚未调用模型'
SAMPLE_TTL_SECONDS = 30


def gate(session):
    row = session.scalar(select(CapacityGate).where(CapacityGate.id == 1)
                         .with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise RuntimeError('Capacity gate missing; apply migrations')
    return row


def pending_bytes(session):
    return int(session.scalar(select(func.coalesce(func.sum(CapacityReservation.bytes), 0)).where(
        CapacityReservation.state.in_(['held', 'published']))))


def reserve(session, identity, kind, owner_id, minimum):
    """No commit: reservation and business claim must succeed or roll back together."""
    policy = gate(session)
    old = session.get(CapacityReservation, identity)
    if old:
        if old.kind != kind or old.owner_id != owner_id or old.bytes < minimum:
            return False
        return old.state == 'held'  # A new cycle must not reuse published/accounted capacity.
    if not policy.enabled:
        return True
    amount = policy.api_bytes if kind == 'api' else policy.cli_bytes
    age = (utcnow() - policy.sample_at.replace(tzinfo=timezone.utc)).total_seconds() if policy.sample_at else -1
    if (not policy.volumes or not 0 <= age <= SAMPLE_TTL_SECONDS or amount < minimum
            or policy.free_bytes - policy.floor_bytes - pending_bytes(session) < amount):
        return False
    session.add(CapacityReservation(id=identity, kind=kind, owner_id=owner_id, bytes=amount))
    session.flush()
    return True


def covered(session, identity, kind, owner_id, minimum):
    """Already admitted work retains capacity even when samples expire or disk fills."""
    policy = gate(session)
    row = session.get(CapacityReservation, identity) if identity else None
    if row:
        return row.kind == kind and row.owner_id == owner_id and row.bytes >= minimum and row.state == 'held'
    return not policy.enabled


def published(session, identity):
    gate(session)
    row = session.get(CapacityReservation, identity) if identity else None
    if row and row.state == 'held':
        row.state, row.published_at = 'published', utcnow()
