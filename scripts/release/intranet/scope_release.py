"""Scope selection and rollback planning for the existing Release state machine."""
from pathlib import Path

import engine
import scope_changes
import scope_engine
import scope_snapshot
import scopes
import snapshot


def selection(data, state, scope):
    if data.get('version') != 2:
        if scope:
            raise RuntimeError('Migrate the verified frontend/ledger before scoped releases')
        return state
    if scope not in data['groups']:
        raise RuntimeError('Select --scope domestic, overseas or shared')
    return scope_snapshot.group(state, scope)


def candidate(u, data, before, release, mode, scope, rollback=False):
    selected = selection(data, before, scope)
    manifest = snapshot.manifest(u, release)
    if not rollback:
        if manifest.get('scope') != scope:
            raise RuntimeError('Package does not match selected business scope')
        scope_changes.check(u, Path(selected['backend']), release, scope, mode)
    return selected


def phase(action, item):
    with scope_engine.context(item['scope'], item['mode'],
                              backend=Path(item['target_backend']), frontend=Path(item['target_frontend']),
                              domestic_publisher=scopes.has_domestic_publisher(item['before'])):
        return getattr(engine, action)()


def unaffected(before, after, scope, mode):
    scope_snapshot.unchanged_other(before, after, scope, mode)


def rollback(tool, scope):
    data = tool.load()
    if scope not in data['groups'] or data['pending']:
        raise RuntimeError('Select an idle business scope for rollback')
    previous = data['groups'][scope]['previous']
    if not previous:
        raise RuntimeError('No previous successful version for selected scope')
    current = data['groups'][scope]['current']
    mode = 'frontend' if previous['backend'] == current['backend'] else 'full'
    # Rebuild from today's global compose. Never replay an old full-site compose
    # that would revert another group's later successful deployment.
    tool.prepare(Path(previous['frontend']), mode, scope, rollback_target=previous)
    return tool.deploy()


def summary(data):
    return {name: {'backend_commit': row['current']['backend_commit'],
                   'frontend_commit': row['current']['frontend_commit'],
                   'previous': bool(row['previous'])} for name, row in data['groups'].items()}
