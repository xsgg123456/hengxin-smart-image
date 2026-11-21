import copy
from types import SimpleNamespace
import pytest

import design_shared_frontend as shared
import overseas_creative_policy as policy
import overseas_creative_history as history
import overseas_design_engine as migration


def manifests(monkeypatch):
    frontend = {'frontend/index.html': 'reviewed'}
    old = {'backend/app/overseas/tasks/models.py': 'old'}
    new = {policy.MIGRATION: 'ddl', 'backend/app/overseas/tasks/models.py': 'new'}
    before = dict(commit=policy.BASE, files=old, runtime_inputs={'cli': 'same'})
    candidate = dict(scope='overseas', commit=policy.CANDIDATE, files={**frontend, **new},
        frontend_current_files=frontend, runtime_inputs=before['runtime_inputs'],
        provenance=dict(source_commit=policy.CANDIDATE, source_files=new, build=dict(
            environment=dict(VITE_RELEASE_SCOPE='overseas', VITE_VERSION=policy.CANDIDATE[:12]))))
    monkeypatch.setattr(policy, 'SOURCE_SHA', policy.digest(new))
    monkeypatch.setattr(policy, 'FRONTEND_SHA', policy.digest(frontend))
    monkeypatch.setattr(policy, 'DELTA_SHA', policy.digest({n: [old.get(n), h] for n,h in new.items()}))
    return before, candidate


def test_pins_sources_assets_delta_and_baseline(monkeypatch):
    before, new = manifests(monkeypatch)
    assert policy.MIGRATION in policy.validate(before, new)
    for changed in ({**new, 'scope':'domestic'}, {**new, 'commit':policy.BASE}, {**new, 'runtime_inputs':{}},
                    {**new, 'files':{**new['files'], 'backend/app/main.py':'foreign'}},
                    {**new, 'frontend_current_files':{'frontend/index.html':'other'}}):
        with pytest.raises(RuntimeError):
            policy.validate(before, changed)
    with pytest.raises(RuntimeError):
        policy.validate(dict(before, commit='old'), new)
    for scope,mode in [('domestic','full'), ('shared','full'), ('overseas','frontend')]:
        with pytest.raises(RuntimeError):
            policy.check(None,None,None,None,scope,mode)


def test_new_owner_guard_and_sql_pin(tmp_path):
    assert "'overseas_0028'" in migration.source_check(policy)
    assert "'overseas_0026'" not in migration.source_check(policy)
    assert policy.SQL_SHA != migration.SQL_SHA
    with pytest.raises(RuntimeError, match='differs'):
        migration.render(SimpleNamespace(RELEASE=tmp_path, native_run=lambda *a,**k:'old or modified SQL'), {}, policy)


def test_history_checks_preservation_and_empty_bindings(monkeypatch):
    rows = {table:[3, 'stable'] for table in history.HISTORY}
    monkeypatch.setattr(history, 'rows', lambda u: rows)
    monkeypatch.setattr(history, 'check_shape', lambda *a: None)
    assert history.capture(None) == rows
    history.verify(None, rows)
    with pytest.raises(RuntimeError):
        history.verify(None, dict(rows, overseas_member_roles=[2, 'changed']))


def test_shared_login_requires_completed_target_and_matching_source(monkeypatch):
    _, new = manifests(monkeypatch)
    candidate = copy.deepcopy(new)
    candidate['scope'] = 'shared'
    candidate['provenance']['build']['environment']['VITE_RELEASE_SCOPE'] = 'shared'
    monkeypatch.setattr(policy, 'SHARED_ASSETS', policy.digest(candidate['frontend_current_files']))
    state = {'groups':{'shared':{'current':{'backend_commit':shared.SHARED_BASE,'frontend_commit':policy.BASE}},
            'overseas':{'current':{'schema':{'overseas':policy.TARGET},'frontend_commit':policy.CANDIDATE,
                                  'backend_commit':policy.CANDIDATE}}}}
    shared.validate(state,new,candidate,policy)
    for field in ('backend_commit', 'frontend_commit'):
        altered = copy.deepcopy(state)
        altered['groups']['overseas']['current'][field] = policy.BASE
        with pytest.raises(RuntimeError):
            shared.validate(altered,new,candidate,policy)
    with pytest.raises(RuntimeError):
        shared.validate(dict(state, pending={'scope':'overseas'}),new,candidate,policy)

def test_schema_preflight_rejects_unknown_roles_and_preexisting_bindings(monkeypatch):
    def before(u, query):
        if 'information_schema.columns' in query:
            return ''
        if 'to_regclass' in query:
            return 'f'
        if 'pg_get_constraintdef' in query:
            return "CHECK (role IN ('super_admin','design_manager','designer'))"
        if 'pg_default_acl' in query:
            return 'SELECT\nUPDATE\nINSERT\nDELETE'
        raise AssertionError(query)
    monkeypatch.setattr(history, 'sql', before)
    history.check_shape(None, False)
    monkeypatch.setattr(history, 'sql', lambda u,q: 't' if 'to_regclass' in q else before(u,q))
    with pytest.raises(RuntimeError, match='table state'):
        history.check_shape(None, False)
    monkeypatch.setattr(history, 'sql', lambda u,q: "'non_designer'" if 'pg_get_constraintdef' in q else before(u,q))
    with pytest.raises(RuntimeError, match='roles constraint'):
        history.check_shape(None, False)

def test_prepare_refuses_changed_overseas_frontend_before_any_maintenance(tmp_path, monkeypatch):
    import domestic_tasks_release as release
    from unittest.mock import Mock

    store = Mock(root=tmp_path)
    tool = release.Upgrade(store, policy)
    current = {'schema': {'overseas': policy.SOURCE}, 'groups': {'overseas': {
        'backend_commit': policy.BASE, 'frontend_commit': 'separately-updated'}}}
    current['images'] = {release.scopes.DOMESTIC_PUBLISHER: 'existing'}
    monkeypatch.setattr(tool.tool, 'load', lambda: {'version': 2, 'current': current})
    monkeypatch.setattr(release.marker, 'guard', lambda *args: None)
    with pytest.raises(RuntimeError, match='baseline'):
        tool.prepare('unused')
    checked_path = Mock(side_effect=RuntimeError('reached path validation'))
    monkeypatch.setattr(release.snapshot, 'release_path', checked_path)
    current['groups']['overseas']['frontend_commit'] = policy.BASE
    with pytest.raises(RuntimeError, match='reached path validation'):
        tool.prepare('unused')
    checked_path.assert_called_once_with('unused')
    store.report.assert_not_called()
