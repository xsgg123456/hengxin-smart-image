"""Read message attribution and immutable reply times without changing history."""
from datetime import timezone
from sqlalchemy import or_, select
from app.overseas.auth.models import Member
from .models import Transcript, Turn


def as_utc(value):
    if value is None:
        return None
    # SQLite drops tzinfo; existing naive values were stored as UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def load(session, turns):
    """Two batch reads, scoped to the turns already authorized by the caller."""
    if not turns:
        return {}, {}
    names = {identity: (name or '').strip() or None for identity, name in session.execute(
        select(Member.id, Member.name).where(Member.id.in_({turn.actor_id for turn in turns})))}
    messages = {}
    rows = session.scalars(select(Transcript).join(Turn, Turn.id == Transcript.turn_id)
        .where(Turn.id.in_([turn.id for turn in turns]), Transcript.kind == 'message',
            or_(Transcript.text == Turn.reply, Turn.reply.is_(None), Turn.reply == ''))
        .order_by(Transcript.id.desc()))
    for row in rows:
        # Transcript IDs define the public stream order, including repeated text.
        messages.setdefault(row.turn_id, row)
    return names, messages


def reply_time(turn, job, message):
    # Mirrors the visible reply: the stored text wins; otherwise public messages
    # remain visible (in the process group for non-successful jobs).
    text = turn.reply or (message.text if message else '')
    if not text.strip():
        return None, None
    if message is not None:
        timestamp = as_utc(message.created_at)
        return timestamp, 'message' if timestamp else None
    timestamp = as_utc(job.completed_at)
    return timestamp, 'completed' if timestamp else None
