"""Only allowlisted messages may cross the execution/public API boundary."""
from sqlalchemy import select
from .models import ExecutionEvent

MESSAGES = {'queued': '等待执行', 'running': '正在执行', 'collecting': '正在校验产物',
            'cancelling': '正在停止执行', 'uncertain': '执行状态待核实，禁止重新执行',
            'succeeded': '执行完成', 'failed': '执行失败，请检查配置或输入后重试', 'cancelled': '执行已取消'}
FAILURES = {
    'invalid_event_stream': '平台解析执行记录失败，已收到的文字已保留，请联系管理员（EVENT_STREAM_INVALID）',
    'authentication_failed': 'Codex 登录凭据已失效，请联系管理员恢复登录后重新提交；本轮未生成可用图片',
    'credentials_invalid': 'Codex 登录凭据不可用，请联系管理员恢复登录后重新提交',
    'credentials_account_changed': 'Codex 登录账号或工作区已变更，请联系管理员恢复原登录后重新提交',
    'credentials_busy': 'Codex 登录凭据正在更新，请稍后重新提交',
    'credentials_refresh_failed': 'Codex 登录已失效或暂时无法更新，请联系管理员恢复登录后重新提交',
    'timeout': '本轮执行超过时限，已停止；请检查要求后重新提交',
    'output_limit': '本轮执行日志超过安全上限，已停止；请联系管理员检查',
    'cancelled': '本轮执行已停止',
    'execution_failed': 'Codex 本轮执行失败，未生成可用图片；请重新提交，若仍失败请联系管理员',
}


def failure_message(value):
    if isinstance(value, str):
        if value in FAILURES:
            return FAILURES[value]
        if value in FAILURES.values():
            return value
    return MESSAGES['failed']


def record(session, job):
    session.add(ExecutionEvent(task_id=job.task_id, job_id=job.id,
                              status=job.status, message=failure_message(job.error)
                              if job.status == 'failed' else MESSAGES[job.status]))


def serialize(job):
    return {'id': str(job.id), 'taskId': str(job.task_id), 'kind': job.kind,
            'status': job.status, 'version': job.version,
            'error': (failure_message(job.error) if job.status == 'failed'
                      else MESSAGES[job.status]) if job.error else None,
            'createdAt': job.created_at, 'startedAt': job.started_at, 'completedAt': job.completed_at}


def read(session, task_id, after=0):
    rows = session.scalars(select(ExecutionEvent).where(ExecutionEvent.task_id == task_id,
        ExecutionEvent.id > after).order_by(ExecutionEvent.id).limit(200)).all()
    return {'items': [{'id': row.id, 'jobId': str(row.job_id), 'status': row.status,
                      'message': failure_message(row.message) if row.status == 'failed'
                      else MESSAGES[row.status], 'createdAt': row.created_at} for row in rows],
            'cursor': rows[-1].id if rows else after}
