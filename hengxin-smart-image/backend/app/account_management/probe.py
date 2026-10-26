"""An isolated, access-only, bounded model probe; no business settings or data."""
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from app.execution.managed_credentials import access_credentials, sync_credentials, CredentialsError
from app.execution.managed_credentials_files import directory
from app.execution.workspace import prepare_workspace, sandbox_command
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
        events = []
        for line in (workspace.control / 'events.jsonl').read_text().splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    events.append(value)
            except ValueError:
                pass
        completed = any(e.get('type') == 'turn.completed' for e in events)
        answered = any(e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'agent_message'
                       and e['item'].get('text', '').strip() == 'HX_AUTH_OK' for e in events)
        if receipt['exit_code'] == 0 and not receipt['reason'] and completed and answered:
            return 'ready'
        # Only explicit auth rejection establishes expiry; do not infer it from timeouts.
        errors = [str(e.get('message', '')) for e in events if e.get('type') == 'error']
        if any('401 Unauthorized' in e or 'token_expired' in e or 'invalid_grant' in e for e in errors):
            return 'expired'
        return 'network'
