"""Reviewed domestic 0044 -> 0045 transition for the ten workspaces."""
import json

import domestic_tasks_policy
import domestic_workspaces_history as history
import scope_changes
import snapshot

SOURCE, TARGET = '0044', '0045'
COMMAND = 'workspaces'
MARKER = 'intranet-domestic-workspaces.json'
RECEIPT = 'workspaces-migration.json'
BASE = '45b1280db608d5676bc24dbf6781763f0ee4b494'
MIGRATION = 'backend/migrations/versions/0045_domestic_workspaces.py'
MIGRATION_SHA = '3cbd3da3d0906d93bc397ca353a550c43b289f0fabadfd19c6a177612ff42c97'
LOGIN = 'backend/app/modules/auth/dingtalk.py'
LOGIN_BEFORE = 'ef7cbbbffd754d9e552117e15487a896b088927261847524edf8ca1e9b6a29a1'
LOGIN_AFTER = 'a20bcca051c83d02c3e34d1fd676d5361180c56b4f3908a4d26a476def9c9214'
# SHA256 of sorted JSON {changed backend path: [baseline hash, candidate hash]}.
BACKEND_DELTA_SHA = '4211fa957d364dbb7927a1a4a9ccdb426a7a5145e112577a183c5a283e86e05e'


def approved_change(name, before, after):
    return (name, before, after) == (LOGIN, LOGIN_BEFORE, LOGIN_AFTER)


def validate(before, candidate):
    validate_locked(before, candidate, BASE, MIGRATION, MIGRATION_SHA, BACKEND_DELTA_SHA)


def validate_locked(before, candidate, base, migration, migration_sha, delta_sha):
    commit = candidate.get('commit')
    if (before.get('commit') != base or candidate.get('scope') != 'domestic' or not commit
            or commit == base or candidate.get('provenance', {}).get('source_commit') != commit):
        raise RuntimeError('Workspaces maintenance requires the reviewed domestic baseline and Git provenance')
    old = scope_changes.backend_files(before)
    new = scope_changes.backend_files(candidate)
    delta = {name: (old.get(name), new.get(name)) for name in old.keys() | new.keys()
             if old.get(name) != new.get(name)}
    digest = snapshot.sha(json.dumps(delta, sort_keys=True, separators=(',', ':')).encode())
    if (digest != delta_sha or delta.get(migration) != (None, migration_sha)
            or before.get('runtime_inputs') != candidate.get('runtime_inputs')):
        raise RuntimeError('Workspaces maintenance requires exactly the reviewed backend and runtime inputs')


def check(original, u, before_root, candidate_root, scope, mode, **kwargs):
    return domestic_tasks_policy.check_reviewed(original, u, before_root, candidate_root, scope, mode,
                                                 MIGRATION, validate, 'workspaces_maintenance', **kwargs)
