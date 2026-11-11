"""Independent success histories; shared artifact ownership uses the existing GC."""
import copy

import cleanup_history
import scope_snapshot
import snapshot


def check(data):
    from catalog import state_sha
    value = data['retention']
    if value.get('version') != 2 or value['state_sha256'] != state_sha(data['current']):
        raise RuntimeError('Scoped catalog live state drift')
    if set(data['groups']) != {'domestic', 'overseas', 'shared'}:
        raise RuntimeError('Incomplete release groups')
    for name, row in data['groups'].items():
        snapshot.same(row['current'], scope_snapshot.group(data['current'], name))
        if value['groups'][name] != state_sha(row):
            raise RuntimeError('Independent success history drift: ' + name)
    return value


def seal(data):
    from catalog import state_sha
    value = data['retention']
    value['state_sha256'] = state_sha(data['current'])
    value['groups'] = {s: state_sha(row) for s, row in data['groups'].items()}


def advance(u, store, old, completed, item):
    from catalog import add_artifact
    value = copy.deepcopy(check(old))
    groups = copy.deepcopy(old['groups'])
    name = item['scope']
    row = groups[name]
    row.update(previous=row['current'], previous_work=row['current_work'],
               current=scope_snapshot.group(completed['current'], name),
               current_work=item['work'], last=item.copy())
    # Non-target versions must not be overwritten by a full-compose backup.
    for other in set(groups) - {name}:
        snapshot.same(groups[other]['current'], scope_snapshot.group(completed['current'], other))
    add_artifact(u, store, value, item['work'], 'transaction', [item['work']])
    value['staged'].pop(item['release'], None)
    value['known_images'] = sorted(set(value['known_images']) | set(completed['current']['images'].values()))
    completed.update(groups=groups, retention=value, previous=None)
    seal(completed)
    check(completed)
    return completed


def protected(data):
    value = check(data)
    sources = set(value['staged']) | set(data.get('migration_pins', []))
    paths = set(data.get('migration_work_pins', []))
    for row in data['groups'].values():
        for key in ('current', 'previous'):
            sources.update(cleanup_history.sources(row[key]))
            if row.get(key + '_work'):
                paths.add(row[key + '_work'])
    if data.get('pending'):
        paths.add(data['pending']['work'])
    return sources | paths, paths


def image_references(data):
    return {v for state in cleanup_history.retained(data) for v in state['images'].values()}
