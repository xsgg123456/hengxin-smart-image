from sqlalchemy import String, cast, func, or_, select

from app.models import utcnow
from app.resource_models import UserRecord
from .files import picture
from .models import ApiAttempt, ApiFile, ApiItem, ApiTask, ApiVersion
from .state import aware


def task_view(session, task):
    items = session.scalars(select(ApiItem).where(ApiItem.task_id == task.id)
                            .order_by(ApiItem.position)).all()
    attempts = session.scalars(select(ApiAttempt).join(ApiItem, ApiAttempt.item_id == ApiItem.id)
                              .where(ApiItem.task_id == task.id)).all()
    generation_seconds = sum(max(0, (aware(a.completed_at or utcnow()) - aware(a.created_at))
                                 .total_seconds()) for a in attempts)
    queue_seconds = max(0, (aware(task.started_at or task.completed_at or utcnow())
                            - aware(task.created_at)).total_seconds())
    def pic(file_id):
        return picture(session.get(ApiFile, file_id)) if file_id else None
    def operator(user_id):
        user = session.get(UserRecord, user_id)
        return user.name if user else '未知用户'
    def version_view(version):
        return {'number': version.number, 'picture': pic(version.file_id),
                'created': aware(version.created_at).isoformat(), 'operator': operator(version.operator_id),
                'text': version.text, 'annotation': pic(version.annotation_id),
                'baseVersion': version.base_version}
    def item_versions(item):
        rows = session.scalars(select(ApiVersion).where(ApiVersion.item_id == item.id)
                                .order_by(ApiVersion.number)).all()
        if rows:
            return [version_view(row) for row in rows]
        if item.result_id:
            return [{'number': 1, 'picture': pic(item.result_id),
                     'created': aware(item.updated_at).isoformat(), 'operator': operator(task.owner_id),
                     'text': task.prompt, 'annotation': None, 'baseVersion': None}]
        return []
    unfinished = [i for i in items if i.state not in {'succeeded', 'failed'}]
    batch_total = (len(items) + 9) // 10
    batch_current = ((unfinished[0].position - 1) // 10 + 1) if unfinished else batch_total
    elapsed = (aware(task.completed_at or utcnow()) - aware(task.created_at)).total_seconds()
    return {'id': str(task.id), 'name': task.name, 'prompt': task.prompt,
            'created': aware(task.created_at).isoformat(), 'status': task.state,
            'operator': operator(task.owner_id),
            'batch': {'current': batch_current, 'total': batch_total,
                      'running': sum(i.state in {'running', 'collecting'} for i in items)},
            'material': pic(task.material_id), 'events': task.events, 'error': task.error,
            'metrics': {'requestCount': len(attempts), 'retryCount': sum(i.retries for i in items),
                        'elapsedSeconds': max(0, elapsed), 'queueSeconds': queue_seconds,
                        'generationSeconds': generation_seconds, 'totalCount': len(items),
                        'successCount': sum(i.state == 'succeeded' for i in items),
                        'firstPassSuccessCount': sum(i.state == 'succeeded' and i.retries == 0 for i in items),
                        'cost': None},
            'items': [{'id': str(i.id), 'position': i.position, 'source': pic(i.source_id),
                       'state': i.state, 'retries': i.cycle_retries, 'error': i.error,
                       'nextAttemptAt': aware(i.next_attempt_at).isoformat() if i.next_attempt_at else None,
                       'result': pic(i.result_id), 'currentVersion': i.current_version or (1 if i.result_id else None),
                       'versions': item_versions(i),
                       'revision': ({'state': i.state, 'text': i.revision_text or '',
                                     'annotation': pic(i.revision_annotation_id),
                                     'operator': operator(i.revision_operator_id),
                                     'baseVersion': i.revision_base_version,
                                     'retries': i.cycle_retries, 'error': i.error}
                                    if i.revision_base_version is not None else None)} for i in items]}


def list_tasks(session, page, size, search, status):
    query = select(ApiTask).where(ApiTask.deleted_at.is_(None))
    if search:
        query = query.where(or_(ApiTask.name.icontains(search, autoescape=True),
                               func.replace(cast(ApiTask.id, String), '-', '').icontains(
                                   search.replace('-', '') or search, autoescape=True),
                               cast(ApiTask.id, String).icontains(search, autoescape=True)))
    if status:
        query = query.where(ApiTask.state == status)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(query.order_by(ApiTask.created_at.desc(), ApiTask.id)
                           .offset((page - 1) * size).limit(size))
    return {'items': [task_view(session, task) for task in rows], 'total': total,
            'page': page, 'pageSize': size}
