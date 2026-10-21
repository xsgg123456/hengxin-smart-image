"""Bound, database-paginated administrative views without private storage fields."""
from datetime import datetime, time, timedelta, timezone
from sqlalchemy import DateTime, String, and_, case, cast, func, literal, or_, select, type_coerce, union_all
from app.modules.api_image_edits.models import ApiItem, ApiTask
from app.modules.api_image_edits.conversation_models import Conversation
from .models import RetentionEntry
from .observability_models import RetentionRecord
from .state import aware

BEIJING = timezone(timedelta(hours=8))
DETAILS = {
    'cache_cleared': '缓存清理完成，会话历史仍保留', 'complete': '历史与待回收文件均已清理',
    'objects_pending': '历史已清理，文件回收中', 'retry': '清理尚未完成，将自动重试',
    'protected': '执行或文件归属尚未确认，已保护并延后检查',
    'waiting': '等待到期', 'due': '已到期，等待下一轮扫描', 'processing': '正在处理',
}
PRESERVED = '保留正式成品、采用版本、归档、原图、素材及调用/Token汇总。'


def history_query():
    r = RetentionRecord
    return select(r.id, r.resource_id, r.task_id, r.task_name, r.image_position, r.kind,
        r.result, r.processed_at, r.last_activity_at, r.due_at, r.next_attempt_at,
        r.turns_removed, r.objects_removed, r.objects_pending,
        or_(ApiTask.id.is_(None), ApiTask.deleted_at.is_not(None)).label('task_deleted'),
        literal('history').label('detail_tab')).outerjoin(ApiTask, ApiTask.id == r.task_id)


def pending_query(session, now):
    e, r = RetentionEntry, RetentionRecord
    is_history = and_(e.status != 'cache_pending', or_(e.status == 'expire_pending',
        e.cache_cleared_at.is_not(None), e.last_activity_at <= now - timedelta(hours=72)))
    kind = case((is_history, 'history'), else_='cache')
    if session.get_bind().dialect.name == 'sqlite':
        due = type_coerce(func.datetime(e.last_activity_at,
            case((is_history, '+72 hours'), else_='+24 hours')), DateTime())
    else:
        due = case((is_history, e.last_activity_at + timedelta(hours=72)),
                   else_=e.last_activity_at + timedelta(hours=24))
    result = func.coalesce(r.result, case((due <= now, 'due'), else_='waiting'))
    entries = select(e.id, e.resource_id, ApiTask.id.label('task_id'), ApiTask.name.label('task_name'),
        ApiItem.position.label('image_position'), kind.label('kind'), result.label('result'),
        r.processed_at, e.last_activity_at, due.label('due_at'),
        case((r.result.in_(('retry', 'protected', 'processing')), e.next_cleanup_at),
             else_=None).label('next_attempt_at'),
        func.coalesce(r.turns_removed, 0).label('turns_removed'),
        func.coalesce(r.objects_removed, 0).label('objects_removed'),
        func.coalesce(r.objects_pending, 0).label('objects_pending'),
        ApiTask.deleted_at.is_not(None).label('task_deleted'), literal('pending').label('detail_tab'))
    entries = entries.join(Conversation, Conversation.id == e.resource_id).join(
        ApiItem, ApiItem.id == Conversation.item_id).join(ApiTask, ApiTask.id == ApiItem.task_id).outerjoin(
        r, and_(r.resource_id == e.resource_id, r.last_activity_at == e.last_activity_at, r.kind == kind))
    entries = entries.where(e.domain == 'api_cli', e.status != 'expired')
    # Physical recovery survives deletion of the original conversation and task.
    objects = history_query().where(r.objects_pending > 0)
    return union_all(entries, objects)


def filtered(session, tab, now, keyword=None, kind=None, result=None, date_from=None, date_to=None):
    rows = (history_query() if tab == 'history' else pending_query(session, now)).subquery()
    query = select(rows)
    if keyword:
        escaped = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.where(or_(rows.c.task_name.ilike('%' + escaped + '%', escape='\\'),
            cast(rows.c.resource_id, String).ilike('%' + escaped.replace('-', '') + '%', escape='\\'),
            cast(rows.c.resource_id, String).ilike('%' + escaped + '%', escape='\\')))
    if kind:
        query = query.where(rows.c.kind == kind)
    if result:
        query = query.where(rows.c.result == result)
    timestamp = rows.c.processed_at if tab == 'history' else rows.c.due_at
    if date_from:
        query = query.where(timestamp >= datetime.combine(date_from, time.min, BEIJING).astimezone(timezone.utc))
    if date_to:
        query = query.where(timestamp < datetime.combine(date_to + timedelta(days=1), time.min,
                                                       BEIJING).astimezone(timezone.utc))
    return query, rows, timestamp


def serialize(row):
    def stamp(value):
        return aware(value).isoformat() if value else None
    return dict(id=str(row['id']), resourceId=str(row['resource_id']),
        taskId=str(row['task_id']) if row['task_id'] else None, taskName=row['task_name'],
        imagePosition=row['image_position'], kind=row['kind'], result=row['result'],
        processedAt=stamp(row['processed_at']), lastActivityAt=stamp(row['last_activity_at']),
        dueAt=stamp(row['due_at']), nextAttemptAt=stamp(row['next_attempt_at']),
        detail=DETAILS[row['result']] + '；' + PRESERVED, turnsRemoved=row['turns_removed'],
        objectsRemoved=row['objects_removed'], objectsPending=row['objects_pending'],
        taskDeleted=row['task_deleted'], detailTab=row['detail_tab'])
