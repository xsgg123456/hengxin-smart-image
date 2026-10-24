"""Settle one approved stopped invocation; no collection, storage or model calls.

Executed using the OLD native worker installation before drain. Keep the result
compatible with 0.2.51: deliveryStatus=null, and an explicit delivery_error.
"""
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import UUID

JOB = '5a190d2a-d2f5-4b20-b72f-2808a5483a1d'
EVENTS_SHA256 = 'e31cbb8d2749dcef06c2100c3b5059d02c6d6fe9df808cb472f7b66181989006'
ACTION = 'studio.output_incident_settle'
NOTICE = '自动保存未完成；模型已正常结束。升级后可通过“取回文件”选择仍存在的原件，无需重新生成。'


def authorize(session, body):
    from app.overseas.auth.models import Member
    from app.overseas.tasks.service import lock_actor
    actor = session.get(Member, UUID(body['actor_id']))
    assert actor is not None, 'Maintenance actor missing'
    lock_actor(session, actor, 'settings.manage')


def settle(session, body):
    from sqlalchemy import select
    from app.core.config import get_settings
    from app.execution.process import same_process
    from app.overseas.execution import claims
    from app.overseas.execution.models import Job, JobOutbox
    from app.overseas.execution.queue import lock_gate
    from app.overseas.management.models import Audit
    from app.overseas.tasks.models import Task, TaskDeletion
    from app.overseas.tasks.cleanup_process import group_alive
    from app.overseas.studio import delivery_context as ctx
    from app.overseas.studio.models import Turn, Conversation, ConversationDeletion
    task_id = session.scalar(select(Job.task_id).where(Job.id == UUID(JOB)))
    task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
    assert task and task.workflow == 'studio' and task.status == 'studio', 'Task not eligible'
    assert not session.get(TaskDeletion, task.id), 'Task deletion exists'
    assert lock_gate(session).paused, 'Execution gate must be paused'
    job = claims.locked_job(session, JOB, gate=False)
    assert job and job.kind == 'studio' and job.task_id == task.id, 'Job ownership mismatch'
    assert job.worker_node == get_settings().worker_node_name, 'Worker ownership mismatch'
    assert job.execution_count == 1 and job.process_exited and not job.cancel_requested, 'Execution facts changed'
    assert job.status == 'uncertain', 'Only the approved uncertain invocation may settle'
    assert all((job.process_id, job.process_boot, job.process_started)), 'Process identity missing'
    assert not same_process(job.process_id, job.process_boot, job.process_started), 'Original process still alive'
    assert not group_alive(job), 'Original process group still alive'
    turn = session.scalar(select(Turn).where(Turn.job_id == job.id).with_for_update())
    assert turn and turn.task_id == task.id and turn.dispatched, 'Turn ownership mismatch'
    channel = session.scalar(select(Conversation).where(Conversation.id == turn.conversation_id).with_for_update())
    assert channel and channel.task_id == task.id, 'Conversation ownership mismatch'
    assert not session.get(ConversationDeletion, channel.id), 'Conversation deletion exists'
    assert job.payload.get('turnId') == str(turn.id) and job.payload.get('conversationId') == str(channel.id), 'Payload ownership mismatch'
    assert session.get(JobOutbox, job.id), 'Dispatch evidence missing'
    assert not session.scalar(select(Audit.id).where(Audit.action == ACTION, Audit.target == JOB)), 'Settlement already audited'
    workspace = ctx.restore(job)
    events = workspace.control / 'events.jsonl'
    assert sha256(events.read_bytes()).hexdigest() == body['events_sha256'], 'Original events changed'
    summary = ctx.success(workspace)
    assert summary.final_text and not turn.event_invalid, 'Complete original reply missing'
    assert channel.session_id in (None, summary.session_id), 'Conversation session drift'
    assert turn.reply in (None, summary.final_text), 'Stored reply drift'
    assert turn.event_session_id in (None, summary.session_id), 'Turn session drift'
    result = dict(job.result or {})
    assert result.get('reply') in (None, summary.final_text), 'Result reply drift'
    assert result.get('sessionId') in (None, summary.session_id), 'Result session drift'
    before = dict(status=job.status, version=job.version, executionCount=job.execution_count,
                  claimToken=str(job.claim_token), eventsSha256=body['events_sha256'], result=result)
    result = dict(result)
    result.pop('deliveryRetryAt', None)
    result.pop('deliveryAttempts', None)
    result.update(reply=summary.final_text, sessionId=summary.session_id, deliveryStatus=None)
    turn.reply, turn.delivery_error = summary.final_text, NOTICE
    channel.session_id = summary.session_id
    claims.end(session, job, 'succeeded', result=result)
    after = dict(status=job.status, version=job.version, executionCount=job.execution_count,
                 deliveryStatus=None, replySha256=sha256(summary.final_text.encode()).hexdigest())
    session.add(Audit(actor_id=UUID(body['actor_id']), action=ACTION, target=JOB, before=before, after=after))
    return after


def execute(packet, factory):
    from app.overseas.db import require_overseas_context
    from app.overseas.execution.queue import lock_gate
    require_overseas_context()
    body, action = packet['request'], packet['action']
    assert body['job_id'] == JOB, 'Only the approved incident job is eligible'
    assert body['events_sha256'] == EVENTS_SHA256, 'Only the approved incident events are eligible'
    with factory.begin() as session:
        authorize(session, body)
        if action == 'settle':
            return settle(session, body)
        gate = lock_gate(session)
        if action == 'inspect':
            return dict(paused=gate.paused)
        if action in ('pause', 'restore'):
            original = packet['original_paused']
            assert type(original) is bool, 'Original gate state missing'
            assert gate.paused == (original if action == 'pause' else True), 'Gate state drift'
            gate.paused = True if action == 'pause' else original
            return dict(paused=gate.paused)
        raise ValueError('Unknown settlement action')


def main():
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables settlement safety assertions')
    import app
    from app.overseas.db import session_factory
    assert Path(app.__file__).resolve().parent.parent == Path.cwd(), 'Different worker installation imported'
    print(json.dumps(execute(json.load(sys.stdin), session_factory())), flush=True)


if __name__ == '__main__':
    main()
