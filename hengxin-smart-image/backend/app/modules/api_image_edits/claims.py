from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from app.models import utcnow
from app.capacity.admission import reserve, covered, WAITING
from .config import get_api_settings
from .models import ApiAttempt, ApiItem, ApiTask
from .deletion_models import ApiTaskDeletion
from .scheduling import IMAGES_PER_TASK, TASK_CONCURRENCY, candidates
from .state import ACTIVE, aware, channel, event, refresh_task, release, release_item
from .retry_policy import database_now, inherit_legacy, exhausted, end_wait, consume, retry_delay
from . import limiter


def recover_expired(session, gate, item, now):
    """Fence an expired owner under the channel lock without resetting its budget."""
    task = session.get(ApiTask, item.task_id)
    attempts = session.scalars(select(ApiAttempt).where(ApiAttempt.item_id == item.id,
        ApiAttempt.retry_cycle_id == item.retry_cycle_id,
        ApiAttempt.state.in_(('running', 'uncertain') if item.state == 'uncertain' else ('running',)))
        .order_by(ApiAttempt.created_at.desc()).limit(1)).all()
    has_result = bool(item.result_url or item.result_bytes)
    for attempt in attempts:
        limiter.outcome(gate, attempt, 'succeeded' if has_result else 'retryable', now)
        attempt.state, attempt.error = ('succeeded', None) if has_result else ('uncertain', 'request_outcome_unknown')
        attempt.completed_at = attempt.completed_at or utcnow()
        from app.modules.management.api_stats.facts import record_attempt
        record_attempt(session, item, task, attempt)
    release_item(item)
    if has_result:
        item.state, item.error = 'collecting', None
        item.retry_reason, item.next_attempt_at = None, None
    elif reason := exhausted(item, now):
        end_wait(item, reason)
    elif attempts or item.state == 'uncertain' or item.retry_policy_version == 'legacy-v1':
        item.state, item.error, item.retry_reason = 'retry_wait', 'request_outcome_unknown', 'retry_wait'
        item.next_attempt_at = now + timedelta(seconds=retry_delay(item))
        item.cycle_retries += 1
    else:
        item.state, item.next_attempt_at = 'queued', None
    event(task, f'第 {item.position} 张执行已恢复')
    refresh_task(session, task)


def adopt_legacy(session, gate):
    """Preserve a pre-upgrade reservation rather than replay an in-flight request."""
    if gate.item_id:
        item = session.get(ApiItem, gate.item_id)
        if item and not item.lease_token:
            item.lease_token, item.lease_until = gate.token, gate.lease_until
        release(gate)


def claim(factory):
    settings = get_api_settings()
    if not settings.enabled:
        return None
    with factory.begin() as session:
        gate = channel(session)
        adopt_legacy(session, gate)
        now = database_now(session)
        # Only admission holds the DB lock; each image owns its network-call lease.
        pending = session.scalars(select(ApiItem).join(ApiTask).where(
            ApiTask.deleted_at.is_(None), ApiItem.state.in_(ACTIVE),
            ~select(ApiTaskDeletion.task_id).where(ApiTaskDeletion.task_id == ApiTask.id).exists())
            .order_by(ApiTask.created_at, ApiTask.id, ApiItem.position)).all()
        if not pending:
            return None
        for item in pending:
            inherit_legacy(session, item)
            if item.state in {'running', 'uncertain'} and not (
                    item.lease_token and item.lease_until and aware(item.lease_until) > now):
                recover_expired(session, gate, item, now)
            if item.state in {'queued', 'retry_wait'} and not (item.result_url or item.result_bytes):
                reason = exhausted(item, now)
                if reason:
                    end_wait(item, reason)
                    refresh_task(session, session.get(ApiTask, item.task_id))
        pending = [item for item in pending if item.state in ACTIVE]
        leased = [item for item in pending if item.state == 'uncertain' or
                  (item.lease_token and item.lease_until and aware(item.lease_until) > now)]
        if len(leased) >= TASK_CONCURRENCY * IMAGES_PER_TASK:
            return None
        for item in candidates(session, pending, leased, False, now):
            if item.state == 'uncertain':
                continue
            if gate.paused and not (item.result_url or item.result_bytes):
                continue
            if item.lease_token and item.lease_until and aware(item.lease_until) > now:
                continue
            if item.next_attempt_at and aware(item.next_attempt_at) > now:
                continue
            cycle = item.capacity_cycle_id or uuid4()
            if not reserve(session, cycle, 'api', item.id, 2 * settings.max_download_bytes):
                item.error, item.next_attempt_at = WAITING, now + timedelta(seconds=5)
                continue
            item.capacity_cycle_id = cycle
            item.lease_token = uuid4()
            item.lease_until = now + timedelta(seconds=settings.lease_seconds)
            item.state = 'collecting' if item.result_url or item.result_bytes else 'running'
            item.next_attempt_at = None
            task = session.get(ApiTask, item.task_id)
            task.state = 'running'
            task.started_at = task.started_at or now
            refresh_task(session, task)
            event(task, f'第 {item.position} 张开始处理')
            return item.id, item.lease_token, item.state
        return None


def owned(session, item_id, token):
    gate = channel(session)
    item = session.get(ApiItem, item_id)
    if not item or item.lease_token != token or not item.lease_until:
        return None, None
    if session.get(ApiTaskDeletion, item.task_id):
        return None, None
    # A receipt may win the lock before recovery revokes this token.
    if aware(item.lease_until) <= database_now(session) and item.state not in {'running', 'uncertain'}:
        return None, None
    return gate, item


def start_attempt(factory, item_id, token, requested_size=None):
    with factory.begin() as session:
        gate, item = owned(session, item_id, token)
        if not item or item.state != 'running' or aware(item.lease_until) <= database_now(session):
            return False
        inherit_legacy(session, item)
        now = database_now(session)
        task = session.get(ApiTask, item.task_id)
        if session.scalar(select(ApiAttempt.id).where(ApiAttempt.item_id == item.id,
                ApiAttempt.state == 'running').limit(1)):
            return False
        reason = exhausted(item, now)
        if reason:
            end_wait(item, reason)
            refresh_task(session, task)
            return False
        reason, due = limiter.waiting(session, gate, now)
        if reason:
            item.state, item.retry_reason, item.next_attempt_at = 'retry_wait', reason, due
            release_item(item)
            refresh_task(session, task)
            return False
        if not covered(session, item.capacity_cycle_id, 'api', item.id,
                       2 * get_api_settings().max_download_bytes):
            item.state, item.error = 'queued', WAITING
            release_item(item)
            return False
        if item.cycle_retries > 0:
            item.retries += 1
        dimensions = tuple(map(int, requested_size.split("x"))) if requested_size else (None, None)
        attempt = ApiAttempt(item_id=item.id,
                             operator_id=item.request_operator_id or item.revision_operator_id or task.owner_id,
                             request_width=dimensions[0], request_height=dimensions[1],
                             retry_cycle_id=item.retry_cycle_id)
        session.add(attempt)
        session.flush()
        consume(item, now)
        task.last_send_at = now
        limiter.granted(gate, attempt, now)
        from app.modules.management.api_stats.facts import record_attempt
        record_attempt(session, item, task, attempt, started=True)
        return True
