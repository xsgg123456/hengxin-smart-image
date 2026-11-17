"""Durable interlock shared by ordinary publishing and cleanup."""
import json

NAME = 'intranet-domestic-tasks.json'
TERMINAL = {'complete', 'cancelled', 'rolled-back'}


def read(u, store):
    path = store.root / NAME
    if not path.exists():
        return None
    u.safe(path)
    row = json.loads(path.read_bytes())
    if not isinstance(row, dict) or not isinstance(row.get('phase'), str):
        raise RuntimeError('Invalid domestic Tasks maintenance marker')
    return row


def guard(u, store):
    row = read(u, store)
    if row and row['phase'] not in TERMINAL:
        raise RuntimeError('Resolve domestic Tasks maintenance using tasks-recover first')
