"""Current API-business queue facts, independent from execution-service observations."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.contracts.api_monitor import ApiMonitorReport
from app.db.session import get_session
from app.models import utcnow, Job
from app.core.config import get_settings
from app.modules.api_image_edits.config import get_api_settings
from app.modules.auth.dependencies import CurrentUser
from app.modules.api_image_edits.models import ApiTask, ApiItem, ApiChannel
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn
from app.modules.api_image_edits.heartbeat_models import ApiWorkerHeartbeat
from app.modules.tasks.attempts import WorkerHeartbeat
from .health import aware, fresh, configured, number
from .settings import values
from app.modules.api_image_edits.scheduling import TASK_CONCURRENCY, IMAGES_PER_TASK

router = APIRouter(tags=['management'])
PHASES = ('queued', 'running', 'retry_wait', 'collecting', 'cancelling', 'uncertain', 'failed')


def observations(session, channel, now):
    model = ApiWorkerHeartbeat if channel == 'api' else WorkerHeartbeat
    try:
        with session.begin_nested():
            beats = session.scalars(select(model)).all()
            result = []
            for beat in beats:
                state = 'unknown'
                if fresh(beat, now):
                    if beat.state == 'unavailable':
                        state = 'unavailable'
                    elif beat.state == 'ready':
                        ready = True if channel == 'api' else configured(beat.dependencies)
                        state = 'available' if ready is True else 'unavailable' if ready is False else 'unknown'
                capacity = beat.capacity if channel == 'api' else beat.dependencies.get('capacity')
                result.append(dict(id=beat.id if channel == 'api' else beat.node,
                    checkedAt=aware(beat.checked_at).isoformat(), state=state,
                    capacity=number(capacity) if fresh(beat, now) else None))
            return result
    except SQLAlchemyError:
        return []


def queue_rows(session, channel, now):
    if channel == 'api':
        query = select(ApiTask.id, ApiTask.name, ApiItem.id, ApiItem.state,
                       ApiItem.next_attempt_at).join(ApiItem, ApiItem.task_id == ApiTask.id)
    else:
        # Current conversation round only: earlier failures never describe a newer success.
        from sqlalchemy.orm import aliased
        newer = aliased(ConversationTurn)
        query = (select(ApiTask.id, ApiTask.name, ApiItem.id, ConversationTurn.status,
                        ConversationTurn.id)
            .join(ApiItem, ApiItem.task_id == ApiTask.id)
            .join(Conversation, Conversation.item_id == ApiItem.id)
            .join(ConversationTurn, ConversationTurn.conversation_id == Conversation.id)
            .where(~select(newer.id).where(newer.conversation_id == Conversation.id,
                (newer.created_at > ConversationTurn.created_at) |
                ((newer.created_at == ConversationTurn.created_at) &
                 (newer.id > ConversationTurn.id))).exists()))
    buckets = {phase: (set(), set(), set()) for phase in PHASES}
    incidents = {}
    for task_id, name, item_id, state, extra in session.execute(query.where(ApiTask.deleted_at.is_(None))):
        phase = ('retry_wait' if channel == 'api' and state == 'queued' and extra
                 and aware(extra) > now else state)
        if phase not in buckets:
            continue
        tasks, images, turns = buckets[phase]
        tasks.add(task_id)
        images.add(item_id)
        if channel == 'cli':
            turns.add(extra)
        if phase in ('retry_wait', 'uncertain', 'failed', 'cancelling'):
            key = (task_id, phase)
            if key not in incidents:
                incidents[key] = dict(taskId=str(task_id), name=name, channel=channel, phase=phase, images=0)
            incidents[key]['images'] += 1
    metrics = [dict(phase=phase, tasks=len(tasks), images=len(images),
                    turns=len(turns) if channel == 'cli' else None)
               for phase, (tasks, images, turns) in buckets.items()]
    return metrics, list(incidents.values())


def build_api_monitor(session, user):
    if user.role not in ('super_admin', 'design_manager'):
        raise HTTPException(403, '仅管理员和设计主管可查看执行监控')
    now, channels, incidents = utcnow(), [], []
    for channel in ('api', 'cli'):
        enabled = get_api_settings().enabled if channel == 'api' else get_settings().enable_codex_executor
        workers = observations(session, channel, now)
        states = [worker['state'] for worker in workers]
        state = ('unavailable' if 'unavailable' in states else 'available'
                 if states and all(value == 'available' for value in states) else 'unknown')
        if not enabled:
            state = 'unavailable'
        extra = dict(paused=None, pauseReason=None, sharedActiveTurns=None, otherActiveTurns=None,
                     concurrencyLimit=TASK_CONCURRENCY if channel == 'api' else None,
                     imagesPerBatch=IMAGES_PER_TASK if channel == 'api' else None)
        try:
            with session.begin_nested():
                metrics, rows = queue_rows(session, channel, now)
                if channel == 'api':
                    gate = session.get(ApiChannel, 1)
                    extra['paused'] = gate.paused if gate else False
                    if gate and gate.paused:
                        extra['pauseReason'] = {'API_KEY_MISSING': 'API 换图密钥尚未配置',
                            'CHANNEL_REJECTED': '上游拒绝调用，请检查密钥、额度和模型配置'}.get(
                                gate.reason, 'API 通道已暂停，请管理员核查配置')
                else:
                    extra['concurrencyLimit'] = values(session)['concurrency']
                    active = dict(session.execute(select(Job.kind, func.count()).where(
                        Job.kind.in_(('generation', 'api_cli_edit')),
                        Job.status.in_(('running', 'collecting', 'cancelling', 'uncertain')))
                        .group_by(Job.kind)).all())
                    extra['sharedActiveTurns'] = sum(active.values())
                    extra['otherActiveTurns'] = active.get('generation', 0)
            queue_state = 'available'
            incidents.extend(rows)
        except SQLAlchemyError:
            queue_state = 'unknown'
            metrics = [dict(phase=phase, tasks=None, images=None, turns=None) for phase in PHASES]
        channels.append(dict(channel=channel, state=state, workers=workers, enabled=enabled,
                             queueState=queue_state, metrics=metrics, **extra))
    return dict(checkedAt=now.isoformat(), channels=channels, incidents=incidents[:100],
                incidentsTruncated=len(incidents) > 100)


@router.get('/management/api-monitor', response_model=ApiMonitorReport)
def api_monitor(user: CurrentUser, session: Session = Depends(get_session)):
    return build_api_monitor(session, user)
