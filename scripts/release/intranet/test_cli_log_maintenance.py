"""Exercise the pinned log package through the ordinary per-group deploy/recovery ledger."""
import copy
import json
from pathlib import Path

import pytest

from test_scope_flow import world
import catalog
import cli_log_maintenance as policy
import release
import scope_catalog
import scope_changes
import scope_snapshot


@pytest.fixture
def fixture(world, monkeypatch):
    def build(scope):
        tool = world.tool
        data = tool.load()
        old_root = Path(data['groups'][scope]['current']['backend'])
        root = world.make('log-change-' + scope, scope, {'backend/app/execution/process.py': b'newline = 1\n'})
        manifests = []
        for source in (old_root, root):
            file = source / 'release-manifest.json'
            m = json.loads(file.read_bytes())
            m['runtime_inputs'] = {'runtime': 'unchanged'}
            m['provenance'].update(source_commit=m['commit'], build={'environment': {'VITE_RELEASE_SCOPE': scope}})
            file.write_text(json.dumps(m))
            manifests.append(m)
        old, new = manifests
        data['current'] = tool.capture(data)
        for side, row in data['groups'].items():
            row['current'] = scope_snapshot.group(data['current'], side)
        scope_catalog.seal(data)
        selected = data['groups'][scope]['current']
        for mapping, value in ((policy.BASE, old['commit']), (policy.FRONTEND, selected['frontend_commit']),
                               (policy.SCHEMA, selected['schema'][scope]), (policy.CANDIDATE, new['commit']),
                               (policy.BASE_INVENTORY, catalog.state_sha(scope_changes.backend_files(old))),
                               (policy.CANDIDATE_INVENTORY, catalog.state_sha(scope_changes.backend_files(new)))):
            monkeypatch.setitem(mapping, scope, value)
        data['retention']['staged'][str(root)] = 'staged.tar.gz'
        tool.save(data)
        return root, data, selected, old, new
    return build


@pytest.mark.parametrize('scope', ('domestic', 'overseas'))
@pytest.mark.parametrize('failure', (None, 'drain', 'no-switch'))
def test_group_backend_only_deploy_and_recover(world, fixture, scope, failure):
    root, before, selected, old, new = fixture(scope)
    tool = world.tool
    with pytest.raises(RuntimeError, match='Model maintenance'):
        tool.prepare(root, 'backend', scope)
    with pytest.raises(RuntimeError, match='unknown ownership'):
        tool.prepare(root, 'full', scope)
    item = tool.prepare(root, 'backend', scope, log_maintenance=True)['pending']
    assert item['maintenance'] == 'cli-logs-20261121'
    assert item['target_frontend'] == selected['frontend']
    world.failure = failure
    if failure:
        with pytest.raises(RuntimeError, match='drain|did not switch'):
            tool.deploy()
        assert tool.recover()['groups'] == before['groups']
    else:
        result = tool.deploy()
        assert result['groups'][scope]['current']['backend_commit'] == new['commit']
        assert result['groups'][scope]['current']['frontend'] == selected['frontend']
        assert result['groups'][scope]['previous'] == selected
        for other in set(before['groups']) - {scope}:
            assert result['groups'][other] == before['groups'][other]
        assert tool.rollback(scope)['groups'][scope]['current'] == selected
    assert world.backups and all(side == scope for side in world.backups)


@pytest.mark.parametrize('bad', ['staged', 'base', 'schema', 'frontend', 'scope', 'commit', 'source',
                                 'build_scope', 'inventory', 'missing_file', 'provenance', 'runtime', 'migration'])
def test_refuse_drift_before_prepare(fixture, bad):
    scope = 'domestic'
    root, data, selected, old, new = fixture(scope)
    # selected is a separate copy because changing the ledger directly would correctly trip catalog.check first.
    selected = copy.deepcopy(selected)
    if bad == 'staged':
        data['retention']['staged'].clear()
    elif bad in ('base', 'schema', 'frontend'):
        selected[{'base': 'backend_commit', 'schema': 'schema', 'frontend': 'frontend_commit'}[bad]] = 'wrong'
    elif bad == 'source':
        new['provenance']['source_commit'] = 'wrong'
    elif bad == 'build_scope':
        new['provenance']['build']['environment']['VITE_RELEASE_SCOPE'] = 'overseas'
    elif bad == 'inventory':
        for values in (new['files'], new['provenance']['source_files']):
            values['backend/app/surprise.py'] = 'extra'
    elif bad == 'missing_file':
        for values in (new['files'], new['provenance']['source_files']):
            del values['backend/app/execution/process.py']
    elif bad == 'provenance':
        new['provenance']['source_files'].pop('backend/app/execution/process.py')
    elif bad == 'runtime':
        new['runtime_inputs'].clear()
    elif bad == 'migration':
        new['files']['backend/migrations/new.sql'] = 'extra'
    else:
        new[bad] = 'wrong'
    with pytest.raises(RuntimeError):
        policy.validate(data, selected, old, new, root, scope)


def test_cli_routes_only_staged_backend_and_rejects_other_modes(world, fixture, monkeypatch):
    root, _, _, _, _ = fixture('domestic')
    monkeypatch.setattr(release.socket, 'gethostname', lambda: 'hengxin-ai-245')
    monkeypatch.setattr(release.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(release, 'retention_store', lambda store: world.store)
    for options in (['--scope', 'shared'], ['--scope', 'domestic', '--mode', 'frontend']):
        with pytest.raises(SystemExit):
            release.main(['prepare-logs', '--release', str(root), *options])
    release.main(['prepare-logs', '--release', str(root), '--scope', 'domestic'])
    item = world.tool.load()['pending']
    assert (item['scope'], item['mode'], item['maintenance']) == ('domestic', 'backend', 'cli-logs-20261121')
