"""Operator-only file recovery. Inspect first; apply requires the same source digest."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.execution.workspace import Workspace
from app.overseas.db import require_overseas_context, session_factory
from app.overseas.execution.models import Job, TERMINAL
from app.overseas.execution.queue import lock_gate
from app.overseas.tasks.models import Task, TaskDeletion
from app.storage.minio_store import get_store
from .files import read
from .models import Conversation, Turn


def recover(factory, conversation_id, *, expected_digest=None, apply=False):
    require_overseas_context()
    conversation_id = UUID(str(conversation_id))
    from .context_workspace import inspect, prepare
    with factory.begin() as session:
        channel = session.get(Conversation, conversation_id)
        if channel is None or not channel.session_id:
            raise ValueError('Existing conversation and session required')
        task = session.scalar(select(Task).where(Task.id == channel.task_id).with_for_update())
        if not task or task.workflow != 'studio' or session.get(TaskDeletion, task.id):
            raise ValueError('Task is not eligible for context recovery')
        lock_gate(session)
        busy = session.scalar(select(Job.id).where(Job.task_id == task.id,
            (Job.status.not_in(TERMINAL)) | ((Job.process_id.is_not(None)) & Job.process_exited.is_(False))).limit(1))
        if busy:
            raise ValueError('Task must be idle before context recovery')
        rows = session.execute(select(Turn, Job).join(Job, Turn.job_id == Job.id).where(
            Turn.conversation_id == channel.id, Turn.dispatched.is_(True)).order_by(Turn.created_at, Turn.id)).all()
        if not rows:
            raise ValueError('No dispatched history to recover')
        for turn, job in rows:
            if (turn.task_id != task.id or job.task_id != task.id or job.kind != 'studio'
                    or job.payload.get('conversationId') != str(channel.id)
                    or job.payload.get('turnId') != str(turn.id)):
                raise ValueError('History ownership mismatch')
        root = Path(get_settings().codex_execution_root).absolute() / 'studio' / str(channel.id)
        history = [dict(turn_id=str(turn.id), inputs=job.payload['inputs']) for turn, job in rows]
        last = history[-1]['turn_id']
        workspace = Workspace(root / 'home', root / 'rounds' / last, root / 'control' / last)
        sessions = workspace.home / '.codex/sessions'
        if sessions.is_symlink() or not any(sessions.rglob('*' + channel.session_id + '*')):
            raise ValueError('Original session files missing')
        plan = inspect(workspace, history)
        from .context_assets import identity, safe_name
        inputs = {}
        for prior in history:
            for item in prior['inputs']:
                key = identity(item)
                inputs[key] = dict(path='/work/inputs/' + key + '/' + safe_name(item['name']),
                    checksum=item['checksum'], size_bytes=item['size_bytes'])
        plan['inputs'] = list(inputs.values())
        if apply:
            if not expected_digest or expected_digest != plan['digest']:
                raise ValueError('Recovery source digest changed; inspect again')
            workspace.maintenance_recovery = True
            prepare(workspace, history, [], lambda data: read(get_store(), SimpleNamespace(**data)))
        return dict(status='restored' if apply else 'inspected', taskId=str(task.id),
            conversationId=str(channel.id), sessionId=channel.session_id, plan=plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('conversation_id')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-digest')
    args = parser.parse_args()
    result = recover(session_factory(), args.conversation_id,
                     expected_digest=args.expected_digest, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
