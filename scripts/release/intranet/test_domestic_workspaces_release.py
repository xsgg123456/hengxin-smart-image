"""0045 cannot borrow the old migration, unblock ordinary release or discard rows."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import domestic_tasks_engine as migration
import domestic_tasks_marker as markers
import domestic_tasks_release as release
import domestic_tasks_policy as previous
import domestic_workspaces_policy as policy
import domestic_workspaces_history as history
import engine
import snapshot


def test_one_time_migration_resumes_committed_schema_without_rerun(tmp_path, monkeypatch):
    before = {'schema': {'domestic': '0044', 'overseas': 'overseas_0026'}, 'data': {'db': 'same'}}
    live = before['schema'].copy()
    def migrate(ctx, *, module, args, cwd, timeout, pass_fds):
        assert module == 'alembic' and args == ('upgrade', '0045') and pass_fds == (99,)
        assert ctx['env']['DOMESTIC_STUDIO_MIGRATION_FENCE'] == '1'
        live['domestic'] = '0045'
        raise RuntimeError('crashed after commit')

    u = SimpleNamespace(WORK=tmp_path, RELEASE=tmp_path, native_run=Mock(side_effect=migrate),
                        safe=lambda path: None, data_identity=lambda: before['data'],
                        write=lambda path, data, **kw: path.write_bytes(data))
    monkeypatch.setattr(engine, 'u', u)
    monkeypatch.setattr(migration.fence, 'assert_held', Mock())
    monkeypatch.setattr(migration, 'stopped', Mock())
    monkeypatch.setattr(migration, 'backup', Mock(return_value='verified backup'))
    monkeypatch.setattr(snapshot, 'schemas', lambda u: live.copy())
    monkeypatch.setattr(history, 'capture', Mock(return_value={'table': [2, 'digest']}))
    monkeypatch.setattr(history, 'verify', Mock())
    ctx = {'hengxin-vps-codex-worker': {'env': {}}}
    with pytest.raises(RuntimeError, match='crashed after commit'):
        migration.migrate(u, ctx, before, 99, policy)
    assert not (tmp_path / previous.RECEIPT).exists()
    migration.check_migration(u, before, 99, policy)
    assert engine._read(policy.RECEIPT)['phase'] == 'migrated'
    history.verify.assert_called_once_with(u, {'table': [2, 'digest']})
    with pytest.raises(RuntimeError, match='Schema/data'):
        migration.migrate(u, ctx, before, 99, policy)
    u.native_run.assert_called_once()


def test_interlocked_commands_require_correct_recovery(tmp_path):
    u, store = SimpleNamespace(safe=lambda p: None), SimpleNamespace(root=tmp_path)
    (tmp_path / policy.MARKER).write_text('{"phase":"forward-required"}')
    for exclude in (None, previous.MARKER):
        with pytest.raises(RuntimeError, match='workspaces-recover'):
            markers.guard(u, store, except_name=exclude)
    markers.guard(u, store, except_name=policy.MARKER)
    (tmp_path / previous.MARKER).write_text('{"phase":"deploying"}')
    with pytest.raises(RuntimeError, match='tasks-recover'):
        markers.guard(u, store, except_name=policy.MARKER)


def test_only_reviewed_shared_login_and_migration_are_admitted(monkeypatch):
    assert policy.approved_change(policy.LOGIN, policy.LOGIN_BEFORE, policy.LOGIN_AFTER)
    assert not policy.approved_change(policy.LOGIN, policy.LOGIN_BEFORE, 'other')
    candidate = {'scope': 'domestic', 'commit': 'c' * 40, 'files': {
        policy.MIGRATION: policy.MIGRATION_SHA, policy.LOGIN: policy.LOGIN_AFTER},
        'provenance': {'source_commit': 'c' * 40}}
    before = {'commit': policy.BASE, 'files': {policy.LOGIN: policy.LOGIN_BEFORE}}
    delta = {policy.MIGRATION: (None, policy.MIGRATION_SHA), policy.LOGIN: (policy.LOGIN_BEFORE, policy.LOGIN_AFTER)}
    digest = snapshot.sha(json.dumps(delta, sort_keys=True, separators=(',', ':')).encode())
    monkeypatch.setattr(policy, 'BACKEND_DELTA_SHA', digest)
    policy.validate(before, candidate)
    for name in ('backend/app/main.py', previous.MIGRATION, policy.LOGIN, policy.MIGRATION):
        changed = copy.deepcopy(candidate)
        changed['files'][name] = 'different'
        with pytest.raises(RuntimeError, match='exactly the reviewed'):
            policy.validate(before, changed)
    with pytest.raises(RuntimeError, match='schema'):
        snapshot.compatible(before, candidate, 'full')


def check_rows(expanded):
    result = []
    for table in sorted(history.TABLES):
        allowed = history.OLD_PRODUCTS | (history.NEW_PRODUCTS if expanded else set())
        if table != 'domestic_studio_archives':
            allowed |= history.OLD_REPLACEMENTS | ({'edit'} if expanded else set())
        items = ', '.join("'" + key + "'::character varying" for key in sorted(allowed))
        result.append([table, table + '_workspace_check', True,
                       '((workspace)::text = ANY ((ARRAY[' + items + '])::text[]))'])
    return result


@pytest.mark.parametrize('expanded', [False, True])
def test_checks_require_exact_set_and_preserve_history(monkeypatch, expanded):
    records = check_rows(expanded)
    monkeypatch.setattr(history, 'sql', lambda *a: '\n'.join(map(json.dumps, records)))
    history.check_constraints(None, expanded)
    records[0][3] += ' OR true'
    with pytest.raises(RuntimeError, match='CHECK values'):
        history.check_constraints(None, expanded)
    records[0] = check_rows(expanded)[0]
    records.pop()
    with pytest.raises(RuntimeError, match='Missing'):
        history.check_constraints(None, expanded)
    monkeypatch.setattr(history, 'check_constraints', Mock())
    monkeypatch.setattr(history, 'rows', lambda u: {'tasks': [1, 'different']})
    with pytest.raises(RuntimeError, match='historical rows changed'):
        history.verify(None, {'tasks': [1, 'original']})


def test_finished_maintenance_never_replays_historical_candidate(monkeypatch, tmp_path):
    tool = release.Upgrade(SimpleNamespace(root=tmp_path), policy)
    row = {'phase': 'complete', 'item': {'work': '/retired'}}
    monkeypatch.setattr(tool, 'read', lambda: row)
    monkeypatch.setattr(tool, 'item', Mock(side_effect=AssertionError('replayed historical work')))
    assert tool.finish() == row
