"""Keep ordinary publish and cleanup away from an incomplete joint upgrade."""
import json

NAME = 'intranet-studio-migration.json'
TERMINAL = {'complete', 'rolled-back', 'cancelled'}


def read(u, store):
    path = store.root / NAME
    if not path.exists():
        return None
    u.safe(path)
    row = json.loads(path.read_bytes())
    if not isinstance(row, dict) or not isinstance(row.get('phase'), str):
        raise RuntimeError('Invalid domestic Studio migration record')
    return row


def guard(u, store):
    row = read(u, store)
    if row and row['phase'] not in TERMINAL:
        raise RuntimeError('Resolve the pending domestic Studio migration first')
