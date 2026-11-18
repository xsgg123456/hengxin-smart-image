"""Release interlock for an incomplete joint Codex runtime switch."""
import json
import re

MARKER = 'intranet-codex-runtime.json'
TERMINAL = ('complete', 'rolled-back')


def load_marker(adapter, store):
    path = store.root / MARKER
    if not path.exists():
        return None
    adapter.safe(path)
    row = json.loads(path.read_bytes())
    if (not isinstance(row, dict) or not re.fullmatch(r'codex-runtime-[0-9]+\.json', row.get('journal', ''))
            or row.get('phase') not in (*TERMINAL, 'running')):
        raise RuntimeError('Invalid Codex runtime maintenance marker')
    return row


def guard(adapter, store):
    marker = load_marker(adapter, store)
    if marker and marker['phase'] not in TERMINAL:
        raise RuntimeError('Resolve pending Codex runtime maintenance with recover')
