"""Maintenance-specific boundaries preserve ordinary ownership/schema rules."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import domestic_tasks_marker as marker
import domestic_tasks_policy as policy
import scope_release
import snapshot


def manifests():
    before = {'commit': policy.BASE, 'scope': 'domestic', 'files': {
        'backend/uv.lock': 'dependencies', 'backend/migrations/versions/0043.py': 'old'}}
    after = copy.deepcopy(before)
    after['commit'] = 'reviewed-new'
    after['files'][policy.MIGRATION] = policy.MIGRATION_SHA
    return before, after


def test_only_exact_migration_addition_is_allowed():
    before, after = manifests()
    policy.validate(before, after)
    with pytest.raises(RuntimeError, match='schema'):
        snapshot.compatible(before, after, 'full')
    snapshot.compatible(after, copy.deepcopy(after), 'full')


@pytest.mark.parametrize('change', ['baseline', 'scope', 'digest', 'dependency', 'migration', 'runtime'])
def test_maintenance_rejects_other_changes(change):
    before, after = manifests()
    if change == 'baseline':
        before['commit'] = 'unknown'
    elif change == 'scope':
        after['scope'] = 'overseas'
    elif change == 'digest':
        after['files'][policy.MIGRATION] = 'unknown'
    elif change == 'dependency':
        after['files']['backend/uv.lock'] = 'new-dependency'
    elif change == 'migration':
        after['files']['backend/migrations/versions/0043.py'] = 'rewritten'
    else:
        after['runtime_inputs'] = {'codex': 'new'}
    with pytest.raises(RuntimeError):
        policy.validate(before, after)


def test_ownership_filter_only_removes_approved_migration(monkeypatch):
    before, after = manifests()
    after['files']['backend/app/shared.py'] = 'unapproved-shared'
    for manifest in (before, after):
        manifest['provenance'] = {'source_files': manifest['files'].copy()}
    monkeypatch.setattr(snapshot, 'manifest', lambda u, root: before if root == 'old' else after)
    def ordinary(u, old, new, scope, mode, tasks_maintenance=False):
        assert tasks_maintenance
        value = snapshot.manifest(u, new)
        assert policy.MIGRATION not in value['files']
        assert policy.MIGRATION not in value['provenance']['source_files']
        assert value['files']['backend/app/shared.py'] == 'unapproved-shared'
        raise RuntimeError('ordinary ownership rejection')
    with pytest.raises(RuntimeError, match='ordinary ownership'):
        policy.check(ordinary, None, 'old', 'new', 'domestic', 'full')
    assert policy.MIGRATION in snapshot.manifest(None, 'new')['files']


def test_login_exception_is_bound_to_exact_path_and_hashes():
    assert policy.approved_change(policy.LOGIN, policy.LOGIN_BEFORE, policy.LOGIN_AFTER)
    assert not policy.approved_change('backend/app/identity/main.py', policy.LOGIN_BEFORE, policy.LOGIN_AFTER)
    assert not policy.approved_change(policy.LOGIN, policy.LOGIN_BEFORE, 'unknown')


def test_pending_marker_blocks_until_verified_terminal(tmp_path):
    u, store = SimpleNamespace(safe=lambda p: None), SimpleNamespace(root=tmp_path)
    for phase in ('preparing', 'deploying', 'forward-required', 'ledger-writing', 'invalid'):
        (tmp_path / marker.NAME).write_text(json.dumps({'phase': phase}))
        with pytest.raises(RuntimeError, match='tasks-recover'):
            marker.guard(u, store)
    for phase in marker.TERMINAL:
        (tmp_path / marker.NAME).write_text(json.dumps({'phase': phase}))
        marker.guard(u, store)


def test_rollback_rejects_schema_mismatch_before_preparing():
    tool = Mock()
    tool.load.return_value = {'pending': None, 'groups': {'domestic': {
        'current': {'schema': {'domestic': '0044'}},
        'previous': {'schema': {'domestic': '0043'}}}}}
    with pytest.raises(RuntimeError, match='schema'):
        scope_release.rollback(tool, 'domestic')
    tool.prepare.assert_not_called()
