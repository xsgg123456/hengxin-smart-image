"""Recognize previously running sources without treating staged candidates as old."""
import json
from pathlib import Path

import snapshot


def sources(state):
    return {state[key] for key in ('backend', 'frontend')} if state else set()


def known(u, store, data):
    result = set(data.get('source_history', []))
    result.update(sources(data.get('current')) | sources(data.get('previous')))
    if data.get('retention'):
        # The catalog imported checksum-bound provenance before any transaction
        # deletion. Reading partly deleted old transactions would break retries.
        return result
    transactions = store.root / 'intranet-transactions'
    if not transactions.exists():
        return result
    u.safe(transactions)
    # Upgrade compatibility: pre-retention transactions saved the original compose.
    # Read only checksum-bound backups of applied transactions, never arbitrary dirs.
    for work in transactions.iterdir():
        u.safe(work)
        if not work.is_dir() or not (work / 'applied.json').exists():
            continue
        if (work / 'web-prepared.json').exists():
            path = work / 'web-prepared.json'
            u.safe(path)
            record = json.loads(path.read_bytes())
            path, digest = work / 'web-before.json', record['before']
        elif (work / 'prepared.json').exists():
            path = work / 'prepared.json'
            u.safe(path)
            record = json.loads(path.read_bytes())
            configs = [c for c in record['configs'] if c['path'] == str(u.COMPOSE)]
            if len(configs) != 1 or Path(configs[0]['backup']).name != configs[0]['backup']:
                raise RuntimeError('Unrecognized historical compose backup')
            path, digest = work / configs[0]['backup'], configs[0]['sha256']
        else:
            raise RuntimeError('Applied transaction lacks preparation evidence')
        u.safe(path)
        raw = path.read_bytes()
        if snapshot.sha(raw) != digest:
            raise RuntimeError('Historical compose backup drift')
        for service in json.loads(raw)['services'].values():
            for mount in service.get('volumes', []):
                if not isinstance(mount, dict) or mount.get('type') != 'bind':
                    continue
                source = Path(mount['source'])
                if mount.get('target') == '/app/app':
                    source = source.parent.parent
                elif mount.get('target') == '/usr/share/nginx/html':
                    source = source.parent
                else:
                    continue
                if source.parent == snapshot.RELEASES:
                    result.add(str(source))
    return result
