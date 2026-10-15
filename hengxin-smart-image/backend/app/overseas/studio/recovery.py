"""Operator-only, evidence-bound repair of a completed text-only false failure.

No model invocation, object writes, new execution lease or completion timestamp.
Call recover inside the installed worker environment; default is read-only.
"""
import json
from hashlib import sha256
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from app.core.config import get_settings
from app.execution.diagnostics import _safe_read, _unique_object
from app.execution.event_json import decode_event
from app.execution.events import MAX_EVENTS_BYTES, parse_events
from app.overseas.db import require_overseas_context
from app.overseas.auth.models import Member
from app.overseas.tasks.models import Task, TaskDeletion
from app.overseas.tasks.service import lock_actor
from app.overseas.execution import claims
from app.overseas.execution.events import MESSAGES, record
from app.overseas.execution.models import JobOutbox
from app.overseas.management.models import Audit
from .models import Turn, Conversation, Picture, Transcript
from .delivery import references
from .execution import HANDLER


def require(condition, message):
    if not condition:
        raise ValueError(message)


def recover(factory, turn_id, actor_id, expected_sha256, *, apply=False):
    require_overseas_context()
    turn_id, actor_id = UUID(str(turn_id)), UUID(str(actor_id))
    with factory.begin() as session:
        actor = session.get(Member, actor_id)
        require(actor is not None, 'Maintenance actor missing')
        lock_actor(session, actor, 'settings.manage')
        turn = session.get(Turn, turn_id)
        require(turn is not None, 'Turn missing')
        task = session.scalar(select(Task).where(Task.id == turn.task_id).with_for_update())
        require(task and task.workflow == 'studio' and task.status == 'studio', 'Task not eligible')
        require(not session.get(TaskDeletion, task.id), 'Task deletion exists')
        job = claims.locked_job(session, turn.job_id)
        require(job and job.task_id == task.id and job.kind == 'studio', 'Job ownership mismatch')
        channel = session.get(Conversation, turn.conversation_id)
        require(channel and channel.task_id == task.id, 'Conversation ownership mismatch')
        require(job.payload.get('turnId') == str(turn.id)
                and job.payload.get('conversationId') == str(channel.id), 'Payload ownership mismatch')
        previous = session.scalar(select(Audit).where(Audit.action == 'studio.text_recovery',
                                                     Audit.target == str(job.id)))
        if previous and job.status == 'succeeded':
            require(previous.after.get('eventSha256') == expected_sha256, 'Evidence changed')
            return dict(status='already_recovered', jobId=str(job.id))
        require(job.status == 'failed' and job.error == MESSAGES['failed']
                and job.result is None and job.process_exited and not job.cancel_requested
                and job.execution_count == 1 and job.completed_at is not None, 'Job not eligible')
        outbox = session.get(JobOutbox, job.id)
        require(outbox and outbox.completed_at is not None, 'Dispatch not closed')
        require(not session.scalar(select(Turn.id).where(Turn.task_id == task.id, Turn.id != turn.id)),
                'Other task turns exist')
        require(not session.scalar(select(Picture.id).where(Picture.task_id == task.id)), 'Pictures exist')
        root = Path(get_settings().codex_execution_root)
        control = root / 'studio' / str(channel.id) / 'control' / str(turn.id)
        path = control / 'events.jsonl'
        raw = _safe_read(path, MAX_EVENTS_BYTES, allow_windows_fallback=True)
        require(sha256(raw).hexdigest() == expected_sha256, 'Event checksum mismatch')
        receipt = json.loads(_safe_read(control / 'exit.json', 4096, allow_windows_fallback=True),
                             object_pairs_hook=_unique_object)
        require(type(receipt.get('exit_code')) is int and receipt['exit_code'] == 0
                and receipt.get('reason') is None, 'CLI did not exit successfully')
        messages, duplicates = {}, 0
        for line in raw.decode('utf-8').splitlines():
            if not line.strip():
                continue
            event = decode_event(line)
            try:
                json.loads(line, object_pairs_hook=_unique_object)
            except ValueError:
                duplicates += 1  # decode_event already restricted the exception's exact shape.
            item = event.get('item', {})
            if event.get('type') == 'item.completed' and item.get('type') == 'agent_message':
                require(isinstance(item.get('id'), str), 'Message identity missing')
                messages[item['id']] = item['text']
        require(duplicates > 0, 'Not the known duplicate-search failure')
        summary = parse_events(path, channel.session_id)
        require(not summary.error and summary.turn_completed and bool(summary.final_text)
                and summary.session_id == channel.session_id == turn.event_session_id,
                'Completion or session mismatch')
        require(turn.reply == summary.final_text and turn.event_offset == len(raw)
                and not turn.event_invalid, 'Stored reply or cursor mismatch')
        require(not list(references(summary.final_text)), 'Image delivery requires separate recovery')
        stored = {row.item_id: row.text for row in session.scalars(select(Transcript).where(
            Transcript.turn_id == turn.id, Transcript.kind == 'message',
            Transcript.state == 'completed').order_by(Transcript.id))}
        require(stored == messages and bool(messages), 'Transcript mismatch')
        require(_safe_read(path, MAX_EVENTS_BYTES, allow_windows_fallback=True) == raw, 'Events changed')
        result = dict(reply=summary.final_text, sessionId=summary.session_id, pictures=[], deliveryError=None)
        report = dict(status='eligible', jobId=str(job.id), eventSha256=expected_sha256,
                      messageCount=len(messages), executionCount=job.execution_count)
        if apply:
            before = dict(status=job.status, error=job.error, version=job.version,
                          completedAt=job.completed_at.isoformat(), executionCount=job.execution_count)
            HANDLER.publish(session, job, result)
            job.status, job.error, job.result = 'succeeded', None, result
            job.version += 1
            record(session, job)
            report['status'] = 'succeeded'
            session.add(Audit(actor_id=actor.id, action='studio.text_recovery', target=str(job.id),
                              before=before, after={**report, 'version': job.version}))
        return report
