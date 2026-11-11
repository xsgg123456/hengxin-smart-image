"""Import real successful versions into independent histories at migration."""
import copy
from pathlib import Path

import catalog
import cleanup_history
import scope_catalog
import scope_snapshot
import scopes
import snapshot


def initialize(u, store, old, after, work):
    value = copy.deepcopy(catalog.check(old))
    data = copy.deepcopy(old)
    data.update(version=2, current=after, previous=None, last=None, pending=None,
                groups={}, migration_pending=True)
    old_state = old['current']
    old_work = value['current']['work']
    value.update(version=2)
    value.pop('current')
    value.pop('previous')
    data['retention'] = value
    for name in scopes.GROUPS:
        now = scope_snapshot.group(after, name)
        # The version immediately before migration was actually served by the
        # old common web. Its bytes remain a valid scoped static rollback target.
        previous = dict(now, **{k: old_state[k] for k in
                        ('backend', 'frontend', 'backend_commit', 'frontend_commit', 'backend_manifest', 'frontend_manifest')})
        data['groups'][name] = {'current': now, 'previous': previous,
                                'current_work': str(work), 'previous_work': old_work, 'last': None}
        value['staged'].pop(now['frontend'], None)
    value['known_images'] = sorted(set(value['known_images']) | set(after['images'].values()))
    data['source_history'] = sorted(set(old.get('source_history', [])) | cleanup_history.sources(after))
    catalog.add_artifact(u, store, value, work, 'transaction', [str(work)])
    scope_catalog.seal(data)
    scope_catalog.check(data)
    return data


def unchanged_original(before, after):
    for kind in ('containers', 'native'):
        for name, identity in before[kind].items():
            if after[kind].get(name) != identity:
                raise RuntimeError('Migration changed existing running service: ' + name)


def check_packages(u, before, releases):
    old = snapshot.manifest(u, before['backend'])
    backend = {n: h for n, h in old['files'].items() if n.startswith('backend/')}
    if set(releases) != set(scopes.GROUPS) or len(set(map(str, releases.values()))) != 3:
        raise RuntimeError('Require three separately staged scope packages')
    for name, root in releases.items():
        current = snapshot.manifest(u, Path(root))
        if current.get('scope') != name:
            raise RuntimeError('Migration package scope mismatch')
        if backend != {n: h for n, h in current['files'].items() if n.startswith('backend/')}:
            raise RuntimeError('First migration must not contain backend changes')
