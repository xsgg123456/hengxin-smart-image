"""Reviewed 0026 -> 0028 release of the overseas studio and feedback workflow."""
import json

import overseas_design_history as history
import scope_changes
import snapshot

SOURCE, TARGET = 'overseas_0026', 'overseas_0028'
SCOPE, COMMAND = 'overseas', 'design'
MARKER, RECEIPT = 'intranet-overseas-design.json', 'design-migration.json'
BASE = 'aef44a628dae49cbb252b1b540e66dcf4c72f6d8'
CANDIDATE = '133f16ae213b1c39f1a4c8b8556a2feb7fb28d49'
# Computed from the official Git archive of 133f16ae and the installed overseas baseline.
SOURCE_SHA = '6bec64990b27cc352b58cfcb8c3906d8561b214a009aad0345a609912637256d'
DELTA_SHA = '04a3ce04a169f0b3db5cef3323787166ebabc89713130d016eb8b7e640606894'
FRONTEND_SHA = 'cd14b6ba9a7190e1acef57eac354d453b617d8c10087422c36a85691ace1a61b'
MIGRATIONS = {
    'backend/migrations/overseas/env.py',
    'backend/migrations/overseas/versions/0027_feedback.py',
    'backend/migrations/overseas/versions/0028_custom_design.py',
    # Already installed domestically. These bytes arrive with the complete Git tree.
    'backend/migrations/versions/0044_domestic_tasks.py',
    'backend/migrations/versions/0045_domestic_workspaces.py',
    'backend/migrations/versions/0046_general_workspace.py',
}


def digest(values):
    return snapshot.sha(json.dumps(values, sort_keys=True, separators=(',', ':')).encode())


def validate(before, candidate):
    provenance = candidate.get('provenance', {})
    environment = provenance.get('build', {}).get('environment', {})
    if (before.get('commit') != BASE or candidate.get('scope') != SCOPE
            or candidate.get('commit') != CANDIDATE or provenance.get('source_commit') != CANDIDATE
            or environment.get('VITE_RELEASE_SCOPE') != SCOPE or environment.get('VITE_VERSION') != CANDIDATE[:12]
            or digest(provenance.get('source_files')) != SOURCE_SHA):
        raise RuntimeError('Overseas design release requires the reviewed sources and overseas baseline')
    current = candidate.get('frontend_current_files')
    if (digest(current) != FRONTEND_SHA
            or any(candidate['files'].get(name) != sha for name, sha in current.items())):
        raise RuntimeError('Overseas design release frontend differs from the reviewed build')
    if not before.get('runtime_inputs') or before['runtime_inputs'] != candidate.get('runtime_inputs'):
        raise RuntimeError('Unexpected runtime inputs in overseas design release')
    old, new = (scope_changes.backend_files(m) for m in (before, candidate))
    delta = {name: (old.get(name), new.get(name)) for name in old.keys() | new.keys()
             if old.get(name) != new.get(name)}
    if digest(delta) != DELTA_SHA or MIGRATIONS != {n for n in delta if n.startswith('backend/migrations/')}:
        raise RuntimeError('Unexpected application, migration or dependency change')
    return sorted(delta)


def check(original, u, before_root, candidate_root, scope, mode, **kwargs):
    if scope != SCOPE or mode != 'full' or any(kwargs.values()):
        raise RuntimeError('Overseas design maintenance is overseas full only')
    before, candidate = (snapshot.manifest(u, root) for root in (before_root, candidate_root))
    changed = validate(before, candidate)
    # Validate actual installed files and their provenance, then attribute the complete
    # historical delta. Only the reviewed files shared with a different runtime qualify.
    old, new = (scope_changes.sources(root, manifest) for root, manifest in
                ((before_root, before), (candidate_root, candidate)))
    old_owners, new_owners = (scope_changes.Imports(code).owners() for code in (old, new))
    for name in set(changed) - MIGRATIONS:
        owners = old_owners.get(name, set()) | new_owners.get(name, set())
        if ((name in old and not old_owners.get(name)) or (name in new and not new_owners.get(name))
                or not owners):
            raise RuntimeError('Unknown application ownership: ' + name)
        if (len(owners) > 1 and not name.startswith('backend/app/overseas/')
                and name not in {'backend/app/execution/workspace.py', 'backend/app/modules/auth/dingtalk.py'}):
            raise RuntimeError('Unreviewed joint source: ' + name)
    return changed
