"""Shared eligibility for detail responses and locked revision acceptance."""
from app.core.config import get_settings
from app.modules.tasks.models import ACTIVE
from sqlalchemy import select
from app.modules.tasks.attempts import ExecutionSession, ExecutionAttempt


def safe_initial_retry(session, task_id):
    attempts = session.scalars(select(ExecutionAttempt).where(ExecutionAttempt.task_id == task_id)).all()
    return bool(attempts) and all(a.status == 'finished' and a.process_id is None for a in attempts)


def eligibility(session, task, current, rounds):
    if any(r.status in ACTIVE for r in rounds):
        reason = ('执行状态待核实，禁止返工或重试' if any(r.status == 'uncertain' for r in rounds)
                  else '任务仍有未结束轮次，请保留意见并等待')
        return False, False, reason
    settings = get_settings()
    enabled = (settings.enable_codex_executor if task.execution_source == 'cli' else
               task.execution_source == 'fixture' and settings.app_env == 'test'
               and settings.enable_fixture_executor)
    if not enabled:
        return False, False, '原任务执行器当前不可用，请保留意见稍后再试'
    failed = current.status in ('failed', 'partial')
    if task.execution_source == 'cli':
        identity = session.get(ExecutionSession, task.id)
        if not identity:
            return False, failed, None if failed else '缺少原会话，无法返工'
        if not identity.session_id:
            if failed and safe_initial_retry(session, task.id):
                return False, True, None
            return False, False, '原会话不可恢复，禁止创建替代会话'
    return current.status in ('succeeded', 'failed', 'partial', 'cancelled'), failed, None
