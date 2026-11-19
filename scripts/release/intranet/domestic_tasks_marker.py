"""Durable interlock shared by ordinary publishing and cleanup."""
import json

import domestic_general_policy as general
import domestic_tasks_policy as tasks
import domestic_workspaces_policy as workspaces

NAME = tasks.MARKER
TERMINAL = {'complete', 'cancelled', 'rolled-back'}


def read(u, store, name=NAME):
    path = store.root / name
    if not path.exists():
        return None
    u.safe(path)
    row = json.loads(path.read_bytes())
    if not isinstance(row, dict) or not isinstance(row.get('phase'), str):
        raise RuntimeError('Invalid domestic Tasks maintenance marker')
    return row


def guard(u, store, except_name=None):
    for transition in (tasks, workspaces, general):
        if transition.MARKER != except_name:
            row = read(u, store, transition.MARKER)
            if row and row['phase'] not in TERMINAL:
                raise RuntimeError(f'Resolve domestic maintenance using {transition.COMMAND}-recover first')
