"""Reviewed, code-only Fast maintenance; never a generic shared-code override.

The two business groups can switch independently: only CLI scheduling changes.
Existing scoped drain, backup, verification and recovery remain mandatory.
"""

COMMIT = '3b38a2c445149d4a0d12c4145cc90f9e173ab4aa'
PATH = 'backend/app/overseas/execution/runner.py'
BEFORE = '3e0f26f97a9e8ad2ed07f06aa239cd57ff76aa1f9c455c9b35bf842058992187'
AFTER = 'b94c5974ae0fa1c879de45150d60d12335a594b11eb808b95677aefa9eb02b7f'


def validate_candidate(manifest, scope, mode):
    if (scope not in ('domestic', 'overseas') or mode != 'full'
            or manifest.get('scope') != scope or manifest.get('commit') != COMMIT
            or manifest.get('files', {}).get(PATH) != AFTER):
        raise RuntimeError('Fast maintenance requires the reviewed scoped Fast package')


def approved_change(name, before, after):
    return name == PATH and before == BEFORE and after == AFTER
