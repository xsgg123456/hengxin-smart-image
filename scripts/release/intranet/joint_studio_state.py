"""Validate and seal the three-scope ledger after a verified Studio upgrade."""
import copy

import catalog
import cleanup_history
import scope_catalog
import scope_snapshot
import scopes
import snapshot


def verify(before, after, backend, frontends, allowed_configs):
    if before['schema'] != {'domestic': '0032', 'overseas': after['schema'].get('overseas')}:
        raise RuntimeError('Unexpected pre-upgrade schema')
    if after['schema'] != {'domestic': '0043', 'overseas': before['schema']['overseas']}:
        raise RuntimeError('Unexpected post-upgrade schema')
    for key in ('data', 'native', 'binaries'):
        if before[key] != after[key]:
            raise RuntimeError('Unapproved runtime identity change: ' + key)
    images = dict(after['images'])
    publisher = images.pop(scopes.DOMESTIC_PUBLISHER, None)
    if (not isinstance(publisher, str) or scopes.DOMESTIC_PUBLISHER in before['images'] or images != before['images']
            or publisher != before['images']['domestic-api']):
        raise RuntimeError('Unexpected container image inventory')
    if set(frontends) != set(scopes.GROUPS):
        raise RuntimeError('Incomplete scoped frontend versions')
    for name in scopes.GROUPS:
        group = after['groups'][name]
        if group['backend'] != str(backend) or group['frontend'] != str(frontends[name]):
            raise RuntimeError('Candidate source did not become live: ' + name)
        if after['asset_fallbacks'][name]['source'] != before['groups'][name]['frontend']:
            raise RuntimeError('Outgoing frontend fallback was not retained: ' + name)
    keys = set(before['configs']) | set(after['configs'])
    if any(before['configs'].get(key) != after['configs'].get(key) for key in keys - set(allowed_configs)):
        raise RuntimeError('Unapproved configuration change')


def advance(u, store, old, after, work, backend, frontends, allowed_configs):
    """Pin the old versions but disallow code rollback across the schema change."""
    if old.get('version') != 2 or old.get('pending'):
        raise RuntimeError('Joint upgrade requires an idle scoped ledger')
    value = copy.deepcopy(scope_catalog.check(old))
    verify(old['current'], after, backend, frontends, allowed_configs)
    data = copy.deepcopy(old)
    pins = set(data.get('migration_pins', []))
    work_pins = set(data.get('migration_work_pins', []))
    for row in old['groups'].values():
        for key in ('current', 'previous'):
            pins.update(cleanup_history.sources(row.get(key)))
            if row.get(key + '_work'):
                work_pins.add(row[key + '_work'])
    work_pins.add(str(work))
    for name in scopes.GROUPS:
        current = scope_snapshot.group(after, name)
        data['groups'][name] = {'current': current, 'previous': None,
                                'current_work': str(work), 'previous_work': None, 'last': None}
        value['staged'].pop(str(frontends[name]), None)
    value['staged'].pop(str(backend), None)
    value['known_images'] = sorted(set(value['known_images']) | set(after['images'].values()))
    catalog.add_artifact(u, store, value, work, 'transaction', [str(work)])
    data.update(current=after, previous=None, pending=None, last=None, retention=value,
                migration_pins=sorted(pins), migration_work_pins=sorted(work_pins), migration_pending=False,
                source_history=sorted(set(data.get('source_history', [])) | cleanup_history.sources(after) | pins))
    scope_catalog.seal(data)
    scope_catalog.check(data)
    return data
