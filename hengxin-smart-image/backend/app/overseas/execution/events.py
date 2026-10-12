"""Only allowlisted messages may cross the execution/public API boundary."""
from sqlalchemy import select
from .models import ExecutionEvent

MESSAGES = {'queued': '等待执行', 'running': '正在执行', 'collecting': '正在校验产物',
            'cancelling': '正在停止执行', 'uncertain': '执行状态待核实，禁止重新执行',
            'succeeded': '执行完成', 'failed': '执行失败，请检查配置或输入后重试', 'cancelled': '执行已取消'}


def record(session, job):
    session.add(ExecutionEvent(task_id=job.task_id, job_id=job.id,
                              status=job.status, message=MESSAGES[job.status]))


def serialize(job):
    return {'id': str(job.id), 'taskId': str(job.task_id), 'kind': job.kind,
            'status': job.status, 'version': job.version,
            'error': MESSAGES[job.status] if job.error else None,
            'createdAt': job.created_at, 'startedAt': job.started_at, 'completedAt': job.completed_at}


def read(session, task_id, after=0):
    rows = session.scalars(select(ExecutionEvent).where(ExecutionEvent.task_id == task_id,
        ExecutionEvent.id > after).order_by(ExecutionEvent.id).limit(200)).all()
    return {'items': [{'id': row.id, 'jobId': str(row.job_id), 'status': row.status,
                      'message': MESSAGES[row.status], 'createdAt': row.created_at} for row in rows],
            'cursor': rows[-1].id if rows else after}
