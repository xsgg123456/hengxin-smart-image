"""Read durable execution facts; never probe a model or the API host's disk."""
from datetime import timezone

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.health import dependency_checks
from app.models import Job, utcnow
from app.execution.diagnostics import _FAILURES, failure_for
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession, WorkerHeartbeat
from app.modules.tasks.models import RoundRecord, TaskRecord
from app.modules.management.settings import values
from app.resource_models import UserRecord

HEARTBEAT_MAX_AGE = 30
RUNNING = ('running', 'collecting', 'cancelling', 'uncertain')
STATES = {'queued': '排队中', 'running': '执行中', 'collecting': '收集结果中',
          'cancelling': '取消中', 'uncertain': '待核实', 'failed': '失败', 'partial': '部分失败'}
# Reuse the authoritative fixed catalog; stored diagnostic prose is never trusted.
PUBLIC_FAILURES = {code: message for code, message, _ in _FAILURES.values()}
LEGACY_MESSAGES = {message: message for message in PUBLIC_FAILURES.values()}


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def fresh(heartbeat, now):
    return 0 <= (now - aware(heartbeat.checked_at)).total_seconds() <= HEARTBEAT_MAX_AGE


def safe_error(value):
    return failure_for(value, 'failed')['message'] if value else None


def diagnostic_error(attempt, round_):
    data = attempt.observation if attempt and isinstance(attempt.observation, dict) else {}
    failure = data.get('failure')
    code = failure.get('code') if isinstance(failure, dict) else None
    if type(code) is str and code in PUBLIC_FAILURES:
        return PUBLIC_FAILURES[code]
    errors = ((attempt.error if attempt else None), round_.error)
    for value in errors:
        if type(value) is not str:
            continue
        diagnostic = failure_for(value, 'failed')
        if diagnostic['code'] != 'UNKNOWN':
            return diagnostic['message']
        if value in LEGACY_MESSAGES:
            return LEGACY_MESSAGES[value]
    return safe_error(next((value for value in errors if value), None)) or (
        safe_error('legacy_failure') if round_.status in ('failed', 'partial') else None)


def number(value):
    return value if type(value) is int and value >= 0 else None


def configured(data):
    values = [data.get(key) for key in ('cli', 'isolation', 'authenticationConfigured')]
    if any(value is False for value in values):
        return False
    return True if all(value is True for value in values) else None


def worker_state(heartbeat, now, active):
    if not fresh(heartbeat, now):
        return 'unknown'
    if heartbeat.state == 'unavailable' or configured(heartbeat.dependencies) is False:
        return 'unavailable'
    if heartbeat.state != 'ready' or configured(heartbeat.dependencies) is None:
        return 'unknown'
    return 'running' if active else 'idle'


def task_rows(session, admin, now):
    query = (select(TaskRecord, RoundRecord, UserRecord.name, ExecutionAttempt, ExecutionSession)
             .join(RoundRecord, TaskRecord.current_round_id == RoundRecord.id)
             .outerjoin(ExecutionAttempt, ExecutionAttempt.round_id == RoundRecord.id)
             .join(UserRecord, UserRecord.id == func.coalesce(
                 ExecutionAttempt.operator_id, RoundRecord.operator_id))
             .outerjoin(ExecutionSession, ExecutionSession.task_id == TaskRecord.id)
             .where(TaskRecord.deleted_at.is_(None),
                    RoundRecord.status.in_(('queued', *RUNNING, 'failed', 'partial')))
             .order_by(RoundRecord.updated_at.desc(), RoundRecord.id))
    total_count = (select(func.count()).select_from(query.order_by(None).subquery())
                   .correlate(None).scalar_subquery().label('total_count'))
    ids = (select(TaskRecord.id).join(RoundRecord, TaskRecord.current_round_id == RoundRecord.id)
           .where(TaskRecord.deleted_at.is_(None)))
    active = ids.where(RoundRecord.status.in_(RUNNING))
    recent = (ids.where(RoundRecord.status.in_(('queued', 'failed', 'partial')))
              .order_by(RoundRecord.updated_at.desc(), RoundRecord.id).limit(100).subquery())
    candidates = active.union_all(select(recent.c.id))
    # Total and candidates share one snapshot, including queued -> running transitions.
    query = query.add_columns(total_count).where(TaskRecord.id.in_(candidates)).order_by(None).order_by(
        case((RoundRecord.status.in_(RUNNING), 0), else_=1),
        RoundRecord.updated_at.desc(), RoundRecord.id)
    rows, task_count = [], 0
    for task, round_, operator, attempt, identity, task_count in session.execute(query):
        started = attempt.started_at if attempt else round_.started_at
        ended = round_.finished_at or now
        rows.append(dict(taskId=str(task.id), name=task.name, operatorName=operator,
                         state=STATES[round_.status],
                         sessionId=identity.session_id if admin and identity else None,
                         elapsedSeconds=max(0, (aware(ended) - aware(started)).total_seconds())
                         if started else None,
                         error=diagnostic_error(attempt, round_)))
    return rows, task_count


def build_monitor(session, user):
    if user.role not in ('super_admin', 'design_manager'):
        raise HTTPException(403, '仅管理员和设计主管可查看执行监控')
    now, admin = utcnow(), user.role == 'super_admin'
    try:
        target = values(session)['concurrency']
        counts = dict(session.execute(select(Job.status, func.count(Job.id))
                      .join(RoundRecord, RoundRecord.job_id == Job.id)
                      .group_by(Job.status)).all())
        queue, running = counts.get('queued', 0), sum(counts.get(key, 0) for key in RUNNING)
        beats = session.scalars(select(WorkerHeartbeat).order_by(WorkerHeartbeat.node)).all()
        active = dict(session.execute(select(ExecutionAttempt.node, func.count(ExecutionAttempt.id))
                      .join(RoundRecord, RoundRecord.id == ExecutionAttempt.round_id)
                      .join(Job, Job.id == RoundRecord.job_id)
                      .where(Job.status.in_(RUNNING), ExecutionAttempt.status.in_(
                          ('starting', 'running', 'uncertain')))
                      .group_by(ExecutionAttempt.node)).all())
        tasks, task_count = task_rows(session, admin, now)
        latest = session.execute(select(ExecutionAttempt, RoundRecord)
                    .join(RoundRecord, RoundRecord.id == ExecutionAttempt.round_id)
                    .where(ExecutionAttempt.finished_at.is_not(None))
                    .order_by(ExecutionAttempt.finished_at.desc()).limit(1)).first()
    except SQLAlchemyError:
        session.rollback()
        return dict(checkedAt=None, state='unknown', queueSize=None, runningCount=None,
                    taskCount=None, tasks=[],
                    detail=None, issue=dict(code='MONITOR_UNAVAILABLE',
                    message='监控数据暂不可用，队列与运行数量未知'))
    # Reuse the existing bounded PG/Redis/MinIO checks, including for supervisors.
    checks = dependency_checks()
    workers = [dict(id=beat.node, checkedAt=aware(beat.checked_at).isoformat(),
                    state=worker_state(beat, now, active.get(beat.node, 0)), queueSize=queue,
                    runningCount=active.get(beat.node, 0),
                    concurrency=min(target, number(beat.dependencies.get('capacity',
                        beat.dependencies.get('concurrency'))) or target)
                    if fresh(beat, now) else 0) for beat in beats]
    states = [worker['state'] for worker in workers]
    if any(value == 'down' for value in checks.values()) or 'unavailable' in states:
        state = 'unavailable'
    elif not states or 'unknown' in states or any(checks.get(key) != 'up'
                                               for key in ('postgresql', 'redis', 'minio')):
        state = 'unknown'
    else:
        state = 'running' if running else 'idle'
    report = dict(checkedAt=now.isoformat(), state=state, queueSize=queue,
                  runningCount=running, taskCount=task_count, tasks=tasks, detail=None)
    if state in ('unavailable', 'unknown'):
        report['issue'] = dict(code='EXECUTION_UNAVAILABLE' if state == 'unavailable'
                               else 'WORKER_UNKNOWN', message='执行服务暂不可用' if state == 'unavailable'
                               else 'Worker 心跳缺失、过期或检查信息不完整，当前状态未知')
    if admin:
        # First release is a single Linux worker. Never substitute local API samples.
        data = beats[0].dependencies if len(beats) == 1 and fresh(beats[0], now) else {}
        last = None
        if latest:
            attempt, round_ = latest
            last = diagnostic_error(attempt, round_) or {
                'succeeded': '执行成功', 'partial': '部分失败', 'failed': '执行失败',
                'cancelled': '执行已取消', 'uncertain': '执行结果待核实',
            }.get(round_.status, '执行已结束，结果未知')
        report['detail'] = dict(workers=workers, cliVersion=data.get('cliVersion'),
            configured=configured(data), lastResult=last, freeDiskBytes=number(data.get('freeDiskBytes')),
            dependencies=[dict(name=name, state={'up': 'available', 'down': 'unavailable'}.get(
                checks.get(name), 'unknown'), message={'up': '连接正常', 'down': '依赖不可达'}.get(
                checks.get(name), '状态未知')) for name in ('postgresql', 'redis', 'minio')])
        capacity = number(data.get('capacity', data.get('concurrency')))
        report['detail']['dependencies'].append(dict(name='workerCapacity',
            state='available' if capacity else 'unknown',
            message='已采样 Worker 容量；并发上限为配置目标且不超过容量' if capacity
            else 'Worker 实际容量未知；并发上限仅代表配置目标，非实际扩容'))
    return report
