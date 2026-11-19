"""Reviewed domestic 0045 -> 0046 transition with a digest-locked application delta."""
import domestic_general_history as history
import domestic_tasks_policy
from domestic_workspaces_policy import validate_locked

SOURCE, TARGET = '0045', '0046'
COMMAND = 'general'
MARKER = 'intranet-domestic-general.json'
RECEIPT = 'general-migration.json'
BASE = '3247094f623124d8d9fdecc3241dbd0f8b102036'
MIGRATION = 'backend/migrations/versions/0046_general_workspace.py'
MIGRATION_SHA = 'efad26fd404b3fe5e81ba2e209fc9b663d85d0889920effae265092df48c2e77'
BACKEND_DELTA_SHA = 'ec075bf43af98fdc893a584a677cc35cd49a22374b2c56d3b19e95656a04a9ac'
SHARED_CHANGES = {
    'backend/app/modules/auth/dingtalk.py': (
        'a20bcca051c83d02c3e34d1fd676d5361180c56b4f3908a4d26a476def9c9214',
        '614505dbbd484dda333f58778df823534f324cec54324f97a6d23ff7a58c9055'),
}


def approved_change(name, before, after):
    return name in SHARED_CHANGES and SHARED_CHANGES[name] == (before, after)


def validate(before, candidate):
    validate_locked(before, candidate, BASE, MIGRATION, MIGRATION_SHA, BACKEND_DELTA_SHA)


def check(original, u, before_root, candidate_root, scope, mode, **kwargs):
    return domestic_tasks_policy.check_reviewed(original, u, before_root, candidate_root, scope, mode,
                                                MIGRATION, validate, 'general_maintenance', **kwargs)
