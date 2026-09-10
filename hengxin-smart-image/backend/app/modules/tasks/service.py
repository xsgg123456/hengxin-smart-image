from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.contracts.business import Accepted
from app.core.config import get_settings
from app.models import Job, Outbox
from app.modules.auth.permissions import authorize
from .idempotency import fingerprint, replay
from .models import RoundRecord, TaskRecord, TaskRequest, TaskSource, ResultSlotRecord
from .snapshots import frozen_input


def available():
    settings = get_settings()
    if not settings.enable_codex_executor and (settings.app_env != 'test' or not settings.enable_fixture_executor):
        raise HTTPException(503, '生成执行器尚未接入，当前不能受理新任务')
    return settings


def enqueue(session, user, task, note, target=None):
    settings = available()
    round_id, job_id = uuid4(), uuid4()
    job = Job(id=job_id, kind='generation', idempotency_key=f'generation:{round_id}',
        payload_hash='0' * 64, value=str(round_id), delay_seconds=settings.fixture_delay_seconds)
    session.add(job)
    session.flush()
    round = RoundRecord(id=round_id, task_id=task.id, job_id=job_id, operator_id=user.id,
        note=note, target=target, status='queued', execution_config={
            'version': 2, 'concurrency': settings.generation_concurrency,
            'timeoutSeconds': settings.codex_timeout_seconds, 'automaticRetries': 0})
    session.add(round)
    session.flush()
    session.add(Outbox(job_id=job_id))
    task.current_round_id = round_id
    return round


def create_task(session, user, body, key):
    authorize(user)
    digest = fingerprint(body)
    previous = replay(session, user.id, 'create', '', key, digest)
    if previous:
        return previous
    available()
    sources, snapshot, skill = frozen_input(session, body)
    task = TaskRecord(name=body.name.strip(), sku=(body.sku or '').strip(), mode=body.mode,
        owner_id=user.id, template_snapshot=snapshot, skill_version_id=skill.id,
        skill_snapshot={'id': str(skill.id), 'version': skill.version, 'checksum': skill.checksum,
                        'name': skill.skill.name},
        execution_source='cli' if get_settings().enable_codex_executor else 'fixture')
    session.add(task)
    session.flush()
    session.add_all([TaskSource(task_id=task.id, slot=i, file_id=f.id, name=f.name)
                     for i, f in enumerate(sources)])
    count = len(snapshot['images']) if snapshot else len(sources)
    session.add_all([ResultSlotRecord(task_id=task.id, slot=i) for i in range(count)])
    round = enqueue(session, user, task, body.note)
    session.add(TaskRequest(user_id=user.id, operation='create', target='', key=key,
        body_hash=digest, task_id=task.id, round_id=round.id))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        previous = replay(session, user.id, 'create', '', key, digest)
        if previous:
            return previous
        raise
    return Accepted(taskId=str(task.id), roundId=str(round.id), state='排队中')


def accept_round(session, user, task_id, body, key):
    """Accept one revision under the shared task lock, with durable replay."""
    authorize(user)
    if body.taskId != str(task_id):
        raise HTTPException(422, '请求任务 ID 与路径不一致')
    digest, target = fingerprint(body), str(task_id)
    previous = replay(session, user.id, 'round', target, key, digest)
    if previous:
        return previous
    task = session.scalar(select(TaskRecord).where(TaskRecord.id == task_id).with_for_update()
                          .execution_options(populate_existing=True))
    if not task or task.deleted_at:
        raise HTTPException(404, '任务不存在')
    # A competing accepted request may have committed while this row lock was waiting.
    previous = replay(session, user.id, 'round', target, key, digest)
    if previous:
        return previous
    from app.modules.revisions.service import eligibility
    rounds = session.scalars(select(RoundRecord).where(RoundRecord.task_id == task_id)).all()
    current = next(r for r in rounds if r.id == task.current_round_id)
    can_revise, can_retry, reason = eligibility(session, task, current, rounds)
    if body.retry:
        if not can_retry:
            raise HTTPException(409, reason or '只有当前已确认失败的轮次可以重试')
        if body.sourceRoundId != str(current.id):
            raise HTTPException(409, '重试来源轮次已过期，请刷新任务详情')
        if body.note != current.note or body.target != current.target:
            raise HTTPException(409, '重试必须沿用原轮次的意见和目标范围')
    elif not can_revise:
        raise HTTPException(409, reason or '当前任务不能返工')
    elif body.sourceRoundId:
        raise HTTPException(422, '普通返工不能指定重试来源')
    if (not body.retry and not body.note.strip()) or len(body.note) > 1000:
        raise HTTPException(422, '返工意见须为1至1000个字符')
    if body.target is not None and session.scalar(select(ResultSlotRecord.id).where(
            ResultSlotRecord.task_id == task.id, ResultSlotRecord.slot == body.target)) is None:
        raise HTTPException(422, '返工目标图片不存在')
    try:
        round = enqueue(session, user, task, body.note, body.target)
        session.add(TaskRequest(user_id=user.id, operation='round', target=target, key=key,
                               body_hash=digest, task_id=task.id, round_id=round.id))
        session.commit()
    except IntegrityError:
        session.rollback()
        previous = replay(session, user.id, 'round', target, key, digest)
        if previous:
            return previous
        raise HTTPException(409, '任务状态已变化，请保留意见并刷新详情')
    return Accepted(taskId=str(task.id), roundId=str(round.id), state='排队中')
