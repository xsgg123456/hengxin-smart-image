"""Receipt transitions run inside the same transaction as cleanup state."""
from sqlalchemy import select, update
from .observability_models import RetentionRecord, RetentionTotals, RetentionObjectLink
from .state import aware, CACHE_AGE, HISTORY_AGE


def ensure_totals(session, now):
    dialect = session.get_bind().dialect.name
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    session.execute(insert(RetentionTotals).values(id='api_cli', since=now,
        cache_total=0, history_total=0).on_conflict_do_nothing(index_elements=['id']))


def receipt(session, task, item, entry, action, now):
    kind = 'history' if action == 'expire_pending' else 'cache'
    record = session.scalar(select(RetentionRecord).where(
        RetentionRecord.resource_id == entry.resource_id,
        RetentionRecord.kind == kind, RetentionRecord.last_activity_at == entry.last_activity_at)
        .with_for_update())
    if record is None:
        ensure_totals(session, now)
        record = RetentionRecord(resource_id=entry.resource_id, task_id=task.id,
            task_name=task.name, image_position=item.position, kind=kind, result='processing',
            last_activity_at=entry.last_activity_at,
            due_at=aware(entry.last_activity_at) + (HISTORY_AGE if kind == 'history' else CACHE_AGE))
        session.add(record)
        session.flush()
    return record


def transition(record, result, now, next_attempt=None):
    record.result, record.processed_at, record.next_attempt_at = result, now, next_attempt


def finish(session, record, now):
    if record.counted:
        return
    if record.objects_pending:
        if record.result not in ('retry', 'protected'):
            transition(record, 'objects_pending', now)
        return
    transition(record, 'complete' if record.kind == 'history' else 'cache_cleared', now)
    record.completed_at = now
    if not record.counted:
        ensure_totals(session, now)
        column = RetentionTotals.history_total if record.kind == 'history' else RetentionTotals.cache_total
        session.execute(update(RetentionTotals).where(RetentionTotals.id == 'api_cli')
                        .values({column: column + 1}))
        record.counted = True


def object_result(session, object_id, now, removed=False, protected=False, next_attempt=None):
    links = session.scalars(select(RetentionObjectLink).where(
        RetentionObjectLink.object_id == object_id).order_by(RetentionObjectLink.record_id)).all()
    for link in links:
        record = session.scalar(select(RetentionRecord).where(RetentionRecord.id == link.record_id)
                                .with_for_update())
        if record is None:
            continue
        if removed:
            record.objects_removed += 1
            record.objects_pending -= 1
            session.delete(link)
            finish(session, record, now)
        else:
            transition(record, 'protected' if protected else 'retry', now, next_attempt)
