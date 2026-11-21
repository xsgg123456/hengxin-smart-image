"""An isolated, access-only, bounded model probe; no business settings or data."""
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from app.execution.managed_credentials import access_credentials, sync_credentials, CredentialsError
from app.execution.managed_credentials_files import directory
from app.execution.workspace import prepare_workspace, sandbox_command
from app.execution.event_file import lines
from app.execution.event_json import decode_event
from app.execution.process import execute


def probe(source, root, binary, bwrap, cancelled=lambda: False):
    try:
        auth = access_credentials(source, 120)
    except CredentialsError:
        # Refresh transport failures and revoked grants share an old error code.
        # Preserve that uncertainty instead of claiming the account was revoked.
        return 'network'
    with tempfile.TemporaryDirectory(prefix='check-', dir=root) as temporary:
        area = Path(temporary)
        with directory(area) as folder:
            folder.write('access.json', json.dumps(auth).encode())
        workspace = prepare_workspace(area / 'workspaces', uuid4(), uuid4(), area / 'access.json', copy_auth=False)
        workspace.use_skill = False
        sync_credentials(area / 'access.json', workspace.home, 120, control=workspace.control.parent)
        command = sandbox_command(workspace, binary, ['exec', '--model', 'gpt-6-astra',
            '-c', 'model_reasoning_effort="low"', '--sandbox', 'read-only',
            '--skip-git-repo-check', '--json', '-'], bwrap=bwrap)
        receipt = execute(command, 'Reply exactly HX_AUTH_OK. Do not use tools or read files.',
                          workspace.control, 120, cancelled, lambda *args: None)
        completed = answered = expired = False
        try:
            for line in lines(workspace.control / 'events.jsonl'):
                try:
                    event = decode_event(line)
                except (ValueError, RecursionError):
                    continue
                kind = event.get('type')
                if kind == 'turn.completed':
                    completed = True
                elif kind == 'item.completed':
                    item = event.get('item')
                    if isinstance(item, dict) and item.get('type') == 'agent_message':
                        answered |= str(item.get('text', '')).strip() == 'HX_AUTH_OK'
                elif kind == 'error':
                    expired |= any(code in str(event.get('message', '')) for code in
                                   ('401 Unauthorized', 'token_expired', 'invalid_grant'))
        except (OSError, ValueError):
            return 'network'
        if receipt['exit_code'] == 0 and not receipt['reason'] and completed and answered:
            return 'ready'
        if expired:
            return 'expired'
        return 'network'
