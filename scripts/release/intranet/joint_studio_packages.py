"""Fail-closed package and migration boundary for the one-time Studio upgrade."""
import ast
from pathlib import Path

import scope_changes
import scopes
import snapshot

VERSIONS = (
    '0033_domestic_studio_bindings.py', '0034_domestic_studio_skill_states.py',
    '0035_domestic_skill_publication_audit.py', '0036_domestic_skill_references.py',
    '0037_domestic_studio_conversations.py', '0038_domestic_studio_turns.py',
    '0039_domestic_studio_outputs.py', '0040_domestic_delivery_retry.py',
    '0041_domestic_studio_archives.py', '0042_domestic_archive_copy_plan.py',
    '0043_domestic_conversation_deletions.py',
)
MIGRATIONS = {'backend/migrations/versions/' + name for name in VERSIONS}
ALLOWED_INPUTS = MIGRATIONS | {'backend/migrations/env.py'}


def check_inputs(old, new):
    before, after = snapshot.backend_inputs(old), snapshot.backend_inputs(new)
    changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
    if (not MIGRATIONS <= changed or changed - ALLOWED_INPUTS
            or MIGRATIONS & before.keys() or not MIGRATIONS <= after.keys()):
        raise RuntimeError('Unexpected dependency or migration inputs')
    if old.get('runtime_inputs') and old['runtime_inputs'] != new.get('runtime_inputs'):
        raise RuntimeError('Runtime inputs changed')


def check_revisions(root):
    for index, name in enumerate(VERSIONS):
        path = Path(root) / 'backend/migrations/versions' / name
        tree = ast.parse(path.read_bytes(), filename=str(path))
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in ('revision', 'down_revision'):
                    if node.targets[0].id in values:
                        raise RuntimeError('Duplicate migration revision assignment')
                    values[node.targets[0].id] = ast.literal_eval(node.value)
        if values != {'revision': str(33 + index).zfill(4), 'down_revision': str(32 + index).zfill(4)}:
            raise RuntimeError('Unexpected migration revision chain')


def verify(u, before, releases):
    if set(releases) != set(scopes.GROUPS) or len(set(map(str, releases.values()))) != len(scopes.GROUPS):
        raise RuntimeError('Three distinct scoped packages are required')
    candidates = {name: snapshot.manifest(u, Path(root)) for name, root in releases.items()}
    if len({package.get('commit') for package in candidates.values()}) != 1:
        raise RuntimeError('Scoped packages must come from one Git commit')
    canonical = None
    for name, package in candidates.items():
        if package.get('scope') != name:
            raise RuntimeError('Package scope mismatch')
        files = scope_changes.backend_files(package)
        if canonical is None:
            canonical = files
        elif files != canonical:
            raise RuntimeError('Scoped packages contain different backend source')
        scope_changes.sources(Path(releases[name]), package)
        old = snapshot.manifest(u, Path(before['groups'][name]['backend']))
        check_inputs(old, package)
    check_revisions(releases['domestic'])
    return candidates
