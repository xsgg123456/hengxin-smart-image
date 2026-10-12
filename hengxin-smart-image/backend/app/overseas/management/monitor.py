from sqlalchemy import func, select
from sqlalchemy.orm import load_only
from app.overseas.execution.events import MESSAGES
from app.overseas.execution.models import Job
from app.overseas.tasks.models import Task
from .facts import image_counts, scoped, token


def read(session, actor, clauses, page, page_size):
    query = scoped(session, actor, clauses)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.execute(query.options(load_only(Job.id, Job.task_id, Job.kind, Job.status,
        Job.execution_count, Job.usage, Job.created_at, Job.started_at, Job.completed_at, Job.error))
        .add_columns(Task.name).order_by(Job.created_at.desc(), Job.id)
                           .offset((page - 1) * page_size).limit(page_size)).all()
    counts = image_counts(session, [job.id for job, _ in rows])
    return {'total': total, 'page': page, 'pageSize': page_size, 'items': [
        {'id': str(j.id), 'taskId': str(j.task_id), 'taskName': name, 'kind': j.kind, 'status': j.status,
         'executionCount': j.execution_count, 'imageCount': counts.get(j.id, 0),
         'inputTokens': token(j, 'input_tokens'), 'outputTokens': token(j, 'output_tokens'),
         'createdAt': j.created_at, 'startedAt': j.started_at, 'completedAt': j.completed_at,
         'error': MESSAGES[j.status] if j.error else None} for j, name in rows]}
