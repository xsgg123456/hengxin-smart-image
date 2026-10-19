"""Archive audit uses authenticated actors, never task ownership metadata."""
from datetime import timezone
from sqlalchemy import select
from app.db.timestamps import utcnow
from .models import ArchiveEvent
from .snapshot import assets


def record_confirmation(session, record, actor, versions, had_versions=False):
    selected = set(versions)
    pictures = [dict(id=str(row.id), name=row.name, sku=row.sku)
                for row in assets(session, record) if row.source_version in selected]
    if len(pictures) != len(selected):
        raise RuntimeError('Archive audit pictures do not match protected assets')
    existing = session.scalar(select(ArchiveEvent.id).where(ArchiveEvent.archive_id == record.id).limit(1))
    now = utcnow()
    event = ArchiveEvent(archive_id=record.id, actor_id=actor.id, actor_name=actor.name,
        pictures=pictures, prior_history_unknown=had_versions and existing is None,
        created_at=now, updated_at=now)
    session.add(event)
    session.flush()


def event_dto(event):
    return dict(id=str(event.id), actorId=str(event.actor_id), actorName=event.actor_name,
                at=event.created_at.replace(tzinfo=timezone.utc) if event.created_at.tzinfo is None else event.created_at, pictures=event.pictures)


def history(session, archive_id):
    rows = session.scalars(select(ArchiveEvent).where(ArchiveEvent.archive_id == archive_id)
        .order_by(ArchiveEvent.created_at.desc(), ArchiveEvent.id.desc())).all()
    return dict(archiveHistory=[event_dto(row) for row in rows],
                historyIncomplete=not rows or any(row.prior_history_unknown for row in rows))
