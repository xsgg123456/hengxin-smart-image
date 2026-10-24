"""Private invocation evidence used to resume collection, never to rerun Codex."""
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from app.core.config import get_settings
from . import context_fs as fs
from .completion import read as parse_events


class UnsuccessfulCompletion(ValueError):
    """A stopped invocation explicitly failed; it cannot enter collection."""


def identity(job):
    return dict(jobId=str(job.id), taskId=str(job.task_id),
                turnId=str(UUID(job.payload['turnId'])),
                conversationId=str(UUID(job.payload['conversationId'])))


def remember(job, workspace):
    record = dict(version=1, identity=identity(job), persistent=bool(getattr(workspace, 'persistent', False)),
                  previous_session=getattr(workspace, 'previous_session', None),
                  native_cursor=getattr(workspace, 'native_cursor', {}),
                  baseline=getattr(workspace, 'baseline', {}))
    fs.save(workspace.control / 'delivery-context.json', record)


def exited(workspace, receipt):
    # The native process writes exit.json before returning; this also durably
    # retains a receipt for adapters and the normal collection path.
    fs.save(workspace.control / 'delivery-exit.json', receipt)


def restore(job):
    owner = identity(job)
    root = Path(get_settings().codex_execution_root).absolute() / 'studio' / owner['conversationId']
    control = root / 'control' / owner['turnId']
    record = fs.load(control / 'delivery-context.json')
    if record.get('version') != 1 or record.get('identity') != owner:
        raise ValueError('Delivery invocation ownership mismatch')
    work = root / 'persistent' / 'work' if record['persistent'] else root / 'rounds' / owner['turnId']
    workspace = SimpleNamespace(home=root / 'home', work=work, control=control,
        persistent=record['persistent'], previous_session=record['previous_session'],
        native_cursor=record['native_cursor'], baseline=record['baseline'], delivered_images=set())
    return workspace


def success(workspace):
    path = workspace.control / 'delivery-exit.json'
    if not path.exists():
        path = workspace.control / 'exit.json'
    receipt = fs.load(path)
    if (type(receipt.get('exit_code')) is int and receipt['exit_code'] != 0) or receipt.get('reason'):
        raise UnsuccessfulCompletion('Process did not complete normally')
    if receipt.get('exit_code') != 0:
        raise ValueError('Delivery requires normal process completion')
    summary = parse_events(workspace.control / 'events.jsonl', workspace.previous_session)
    if summary.error or not summary.turn_completed or not summary.session_id or summary.final_text is None:
        raise ValueError('Delivery requires a complete final response')
    return summary


def close_native(workspace, session_id):
    path = workspace.control / 'delivery-native-end.json'
    if path.exists():
        workspace.native_end_cursor = fs.load(path)
        return
    from .native_images import snapshot
    try:
        cursor = snapshot(workspace.home, session_id)
    except (OSError, ValueError):
        # Explicit final file links do not require a second native event parser.
        return
    fs.save(path, cursor)
    workspace.native_end_cursor = cursor
