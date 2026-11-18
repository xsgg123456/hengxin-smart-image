"""Narrow, reviewed domestic 0043 -> 0044 transition; no override flag."""
import copy

import scopes
import snapshot
import domestic_tasks_history as history

SOURCE, TARGET = '0043', '0044'
COMMAND = 'tasks'
MARKER = 'intranet-domestic-tasks.json'
RECEIPT = 'tasks-migration.json'

BASE = 'c79924625230275bad65fa778020d5b4a3b272e0'
MIGRATION = 'backend/migrations/versions/0044_domestic_tasks.py'
MIGRATION_SHA = 'c6a9fb63e97f4b9460ebc37667a4116ae72bd380574f7baa0770093534bf0d01'
LOGIN = 'backend/app/modules/auth/dingtalk.py'
LOGIN_BEFORE = '7b60c964a4b54c9d29ae55aadf8ed739f7c37cbcbabb8dbb8dce079a8e86bc1d'
LOGIN_AFTER = 'ef7cbbbffd754d9e552117e15487a896b088927261847524edf8ca1e9b6a29a1'


def approved_change(name, before, after):
    return name == LOGIN and before == LOGIN_BEFORE and after == LOGIN_AFTER


def validate(before, candidate):
    if before.get('commit') != BASE or candidate.get('scope') != 'domestic':
        raise RuntimeError('Tasks maintenance requires the reviewed domestic source baseline')
    if (MIGRATION in before['files']
            or candidate['files'].get(MIGRATION) != MIGRATION_SHA):
        raise RuntimeError('Tasks migration digest differs from the reviewed 0044 migration')
    old, new = snapshot.backend_inputs(before), snapshot.backend_inputs(candidate)
    new.pop(MIGRATION, None)
    if old != new or before.get('runtime_inputs') != candidate.get('runtime_inputs'):
        raise RuntimeError('Unapproved migration, dependency or runtime input change')


def check(original, u, before_root, candidate_root, scope, mode, **kwargs):
    return check_reviewed(original, u, before_root, candidate_root, scope, mode,
                          MIGRATION, validate, 'tasks_maintenance', **kwargs)


def check_reviewed(original, u, before_root, candidate_root, scope, mode,
                   migration, validator, flag, **kwargs):
    if scope != 'domestic' or mode != 'full' or kwargs.get('fast_maintenance'):
        raise RuntimeError('Tasks maintenance is domestic full only')
    reader = snapshot.manifest
    before, candidate = reader(u, before_root), reader(u, candidate_root)
    validator(before, candidate)

    def filtered(adapter, root):
        value = copy.deepcopy(reader(adapter, root))
        # Only the single hash-locked migration is removed from the ordinary
        # ownership comparison. All app files keep normal reachability checks.
        value['files'].pop(migration, None)
        value.get('provenance', {}).get('source_files', {}).pop(migration, None)
        return value

    with scopes.replace(snapshot, manifest=filtered):
        return original(u, before_root, candidate_root, scope, mode, **{flag: True})
