"""Model maintenance accepts only its complete reviewed delta and retains live UI."""
import json

import pytest

from test_scope_changes import releases
from test_scope_flow import world, publish
import model_maintenance as policy
import scope_changes
import scopes
import snapshot


@pytest.fixture
def pair(releases, monkeypatch):
    base, _, write, u = releases
    names = list(policy.CHANGES)
    old = {n: b'VALUE = 1\n' for n in names}
    new = {n: b'VALUE = 2\n' for n in names}
    monkeypatch.setattr(policy, 'CHANGES', {n: (snapshot.sha(old[n]), snapshot.sha(new[n])) for n in names})
    imports = ''.join('import ' + n.removeprefix('backend/').removesuffix('.py').replace('/', '.') + '\n'
                      for n in names)
    base['backend/app/main.py'] = base['backend/app/overseas/main.py'] = imports.encode()

    def create(scope, *, old_extra=None, new_extra=None, baseline=None, package_scope=None,
               commit='1' * 40, source_commit='1' * 40):
        before = write('old', {**base, **old, **(old_extra or {})})
        after = write('new', {**base, **new, **(new_extra or {})})
        for root, metadata in ((before, {'commit': baseline or policy.BASE[scope]}),
                               (after, {'scope': package_scope or scope, 'commit': commit})):
            path = root / 'release-manifest.json'
            manifest = json.loads(path.read_bytes())
            if root == after:
                manifest['provenance']['source_commit'] = source_commit
            path.write_text(json.dumps({**manifest, **metadata}))
        return u, before, after
    return create


@pytest.mark.parametrize('scope', ['domestic', 'overseas'])
def test_shared_changes_require_exact_model_command(pair, scope):
    args = pair(scope)
    with pytest.raises(RuntimeError, match='shared/joint'):
        scope_changes.check(*args, scope, 'full')
    assert set(scope_changes.check(*args, scope, 'backend')) == set(policy.CHANGES)


@pytest.mark.parametrize('adjustments', [
    {'baseline': policy.BASE['overseas']}, {'package_scope': 'overseas'},
    {'commit': policy.BASE['domestic'], 'source_commit': policy.BASE['domestic']},
    {'source_commit': '2' * 40},
    {'new_extra': {'backend/app/main.py': b'VALUE = 3\n'}},
    {'old_extra': {next(iter(policy.CHANGES)): b'unknown baseline\n'}},
    {'new_extra': {next(iter(policy.CHANGES)): b'unknown candidate\n'}},
    {'new_extra': {next(iter(policy.CHANGES)): b'VALUE = 1\n'}},
    {'new_extra': {'backend/uv.lock': b'version = 2\n'}},
])
def test_model_refuses_scope_baseline_missing_extra_and_wrong_hash(pair, adjustments):
    args = pair('domestic', **adjustments)
    with pytest.raises(RuntimeError, match='Model maintenance|Dependency/schema'):
        scope_changes.check(*args, 'domestic', 'backend')


@pytest.mark.parametrize('scope', ['domestic', 'overseas'])
@pytest.mark.parametrize('failure', [None, 'drain', 'no-switch'])
def test_backend_only_separate_frontend_history_deploy_rollback_and_recovery(world, monkeypatch, scope, failure):
    w = world
    before = publish(w, 'frontend-update', scope)
    candidate = w.make('model', scope)
    selected = before['groups'][scope]['current']
    assert selected['frontend'] != selected['backend']
    old_compose = json.loads(w.u.COMPOSE.read_bytes())
    monkeypatch.setattr(scope_changes, 'check', lambda *args, **kw: None)
    item = w.tool.prepare(candidate, 'backend', scope)['pending']
    assert item['maintenance'] == 'codex-model-20261118'
    assert item['target_frontend'] == selected['frontend']
    w.failure = failure
    if failure:
        with pytest.raises(RuntimeError, match='drain|did not switch'):
            w.tool.deploy()
        assert w.tool.recover()['groups'] == before['groups']
    else:
        result = w.tool.deploy()
        assert result['groups'][scope]['current']['backend'] == str(candidate)
        assert result['groups'][scope]['current']['frontend'] == selected['frontend']
        assert result['groups'][scope]['previous'] == selected
        for other in set(scopes.GROUPS) - {scope}:
            assert result['groups'][other] == before['groups'][other]
        assert json.loads(w.u.COMPOSE.read_bytes())['services'][scopes.UI[scope]] == old_compose['services'][scopes.UI[scope]]
        reverted = w.tool.rollback(scope)
        assert reverted['groups'][scope]['current'] == selected
        assert reverted['last']['mode'] == 'backend'
        assert w.tool.rollback(scope)['groups'][scope]['current'] == result['groups'][scope]['current']
    assert all(scopes.UI[scope] not in apps for apps, _ in w.transitions[1:])
    assert w.backups and all(side == scope for side in w.backups)
