"""Private invocation evidence for recovering output without rerunning Codex."""
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from app.overseas.studio import context_fs as fs
from app.overseas.studio.delivery_context import success


def identity(job_id, owner_id, channel_id, turn_id):
    return dict(jobId=str(UUID(str(job_id))), taskId=str(UUID(str(owner_id))),
                conversationId=str(UUID(str(channel_id))), turnId=str(UUID(str(turn_id))))


def remember(workspace, owner):
    owner = identity(owner['jobId'], owner['taskId'], owner['conversationId'], owner['turnId'])
    if (workspace.home.parent.name != owner['conversationId']
            or workspace.control.name != owner['turnId']):
        raise ValueError('Domestic Studio workspace identity mismatch')
    record = dict(version=1, identity=owner, previous_session=workspace.previous_session,
                  native_cursor=workspace.native_cursor, baseline=workspace.baseline)
    path = workspace.control / 'domestic-delivery-context.json'
    if path.exists():
        if fs.load(path) != record:
            raise ValueError('Domestic Studio delivery context changed')
    else:
        fs.save(path, record)


def restore(root, owner):
    owner = identity(owner['jobId'], owner['taskId'], owner['conversationId'], owner['turnId'])
    base = Path(root).absolute() / 'domestic-studio' / owner['conversationId']
    control = fs.checked(base / 'control' / owner['turnId'], directory=True)
    record = fs.load(control / 'domestic-delivery-context.json')
    if record.get('version') != 1 or record.get('identity') != owner:
        raise ValueError('Domestic Studio delivery context ownership mismatch')
    workspace = SimpleNamespace(home=fs.checked(base / 'home', directory=True),
        work=fs.checked(base / 'persistent' / 'work', directory=True), control=control,
        persistent=True, previous_session=record['previous_session'],
        native_cursor=record['native_cursor'], baseline=record['baseline'], delivered_images=set())
    return workspace
