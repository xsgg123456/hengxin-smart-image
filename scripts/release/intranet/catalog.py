"""One retention clock: the latest two successful deployment snapshots."""
import copy
import json
from pathlib import Path

import artifact_gc
import catalog_import
import cleanup_history
import image_gc
import snapshot


def state_sha(state):
    return snapshot.sha(json.dumps(state, sort_keys=True, separators=(',', ':')).encode())


def record(state, images, work=None):
    return {'state_sha256': state_sha(state), 'images': images, 'work': work}


def check(data):
    if data.get('version') == 2:
        from scope_catalog import check as scoped_check
        return scoped_check(data)
    value = data['retention']
    if value.get('version') != 1:
        raise RuntimeError('Unknown complete-deployment catalog')
    for name in ('current', 'previous'):
        row, state = value[name], data[name]
        if (row is None) != (state is None) or (state and row['state_sha256'] != state_sha(state)):
            raise RuntimeError('Complete deployment catalog drift: ' + name)
    return value


def journal_identity(path):
    path = Path(path)/'started.json'
    if not path.exists():
        return None
    value = json.loads(path.read_bytes())
    if not {'prepared', 'ctx'} <= value.keys():
        return None
    return state_sha({k: v for k, v in value.items()
                      if k not in ('phase', 'recovering', 'paused', 'sockets')})


def add_artifact(u, store, value, path, kind, owners):
    path = Path(path)
    proof = artifact_gc.proof(u, store, path, kind)
    existing = value['artifacts'].get(str(path))
    if existing and existing['proof'] != proof:
        raise RuntimeError('Registered publication artifact changed')
    value['artifacts'][str(path)] = {'proof': proof,
        'owners': sorted(set(owners) | set(existing['owners'] if existing else []))}
    if kind == 'transaction':
        value['artifacts'][str(path)]['journal_identity'] = journal_identity(path)


def bootstrap(u, store, data):
    data = copy.deepcopy(data)
    if data.get('retention'):
        check(data)
        return data
    if data.get('pending'):
        raise RuntimeError('Resolve pending deployment before catalog initialization')
    images = image_gc.capture(u)
    if any(images.get(n) != identity for n, identity in data['current']['images'].items()):
        raise RuntimeError('Live images differ from verified deployment')
    previous = None
    if data['previous']:
        if data['previous']['data'] != data['current']['data']:
            raise RuntimeError('Cannot infer previous infrastructure images; explicit upgrade inventory required')
        prior = dict(images, **data['previous']['images'])
        previous = record(data['previous'], prior)
    value = {'version': 1, 'current': record(data['current'], images), 'previous': previous,
             'known_images': sorted(set(images.values()) | set(previous['images'].values() if previous else [])),
             'artifacts': {}, 'staged': {}, 'unowned': []}
    sources = cleanup_history.sources(data['current']) | cleanup_history.sources(data['previous'])
    found, value['unowned'] = catalog_import.discover(u, store, sources)
    value['current']['work'] = data['last']['work'] if data.get('last') else None
    if value['current']['work'] and found.get(value['current']['work'], {}).get('source') != data['current']['frontend']:
        raise RuntimeError('Current successful transaction lacks matching applied evidence')
    if previous:
        # Pre-catalog migration accepts only an unambiguous, checksum-bound
        # applied transaction matching the previous frontend. Never guess by age.
        matches = [p for p, row in found.items() if row['kind'] == 'transaction'
                   and row.get('source') == data['previous']['frontend']
                   and p != value['current']['work']]
        if len(matches) != 1:
            raise RuntimeError('Previous successful transaction cannot be identified unambiguously')
        previous['work'] = matches[0]
    history = cleanup_history.known(u, store, data)
    for path, item in found.items():
        add_artifact(u, store, value, path, item['kind'], item['owners'])
        if item.get('source'):
            history.add(item['source'])
    data.update(retention=value, source_history=sorted(history))
    return data


def before(u, store, data):
    data = bootstrap(u, store, data)
    if data.get('version') == 2:
        fleet, expected = image_gc.scoped(u), data['current']['images']
    else:
        fleet, expected = u, data['retention']['current']['images']
    if image_gc.capture(fleet) != expected:
        raise RuntimeError('Complete deployment image fleet drift')
    return data


def stage(u, store, data, source, archive):
    value = check(data)
    add_artifact(u, store, value, archive, 'package', [str(source)])
    value['staged'][str(source)] = str(archive)


def advance(u, store, old, completed, item):
    """Called after runtime checks, inside the same atomic success-ledger update."""
    if old.get('version') == 2:
        from scope_catalog import advance as scoped_advance
        return scoped_advance(u, store, old, completed, item)
    value = copy.deepcopy(check(old))
    images = image_gc.capture(u)
    # Ordinary source releases may not silently upgrade any of the 17 runtimes.
    if images != value['current']['images']:
        raise RuntimeError('Runtime images changed during source deployment')
    value.update(previous=value['current'], current=record(completed['current'], images, item['work']))
    value['known_images'] = sorted(set(value['known_images']) | set(images.values()))
    value['staged'].pop(item['release'], None)
    add_artifact(u, store, value, item['work'], 'transaction', [item['work']])
    completed['retention'] = value
    return completed


def recover(data):
    """Match the saved before-state, without inventing a new success or losing ownership."""
    value = data.get('retention')
    if data.get('version') == 2:
        check(data)
        return
    if not value:
        return
    if value['current']['state_sha256'] != state_sha(data['current']):
        if not value['previous'] or value['previous']['state_sha256'] != state_sha(data['current']):
            raise RuntimeError('Recovery does not match either retained deployment')
        value['current'] = value['previous']
    if data['previous'] is None:
        value['previous'] = None
    check(data)


def finished_attempt(u, store, data, item):
    """Register verified recovery/cancellation without advancing the success clock."""
    if not data.get('retention') or not Path(item['work']).exists():
        return
    value = check(data)
    old = value['artifacts'].get(item['work'])
    if old:
        actual = artifact_gc.proof(u, store, Path(item['work']), 'transaction')
        expected = old['proof']
        # Engine recovery journals phase/drain/socket progress in started.json.
        # Its prepared binding and original execution context remain immutable.
        mutable = set()
        if (item.get('mode') == 'full' or item.get('scope')) and old.get('journal_identity'):
            journal = json.loads((Path(item['work'])/'started.json').read_bytes())
            if (journal_identity(item['work']) != old['journal_identity']
                    or journal.get('recovering') is not True
                    or journal.get('phase') not in ('ingress', 'recovering')
                    or 'rolled-back.json' not in actual['files']):
                raise RuntimeError('Recovery journal identity drift')
            mutable.add('started.json')
        if (actual['identity'] != expected['identity'] or actual['dirs'] != expected['dirs']
                or any(actual['files'].get(k) != v for k, v in expected['files'].items() if k not in mutable)
                or set(actual['files']) - set(expected['files']) - {'rolled-back.json'}):
            raise RuntimeError('Recovered transaction content drift')
        old['proof'] = actual
    else:
        add_artifact(u, store, value, item['work'], 'transaction', [item['work']])


def protected(data):
    if data.get('version') == 2:
        from scope_catalog import protected as scoped_protected
        return scoped_protected(data)
    value = check(data)
    sources = cleanup_history.sources(data['current']) | cleanup_history.sources(data['previous'])
    sources.update(value['staged'])
    paths = set()
    for name in ('current', 'previous'):
        if value[name] and value[name].get('work'):
            paths.add(value[name]['work'])
            sources.add(value[name]['work'])
    for name in ('last', 'pending'):
        if data.get(name):
            paths.add(data[name]['work'])
    return sources, paths
