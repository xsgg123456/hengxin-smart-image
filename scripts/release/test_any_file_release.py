"""No-migration release fault matrix; production operations are mocked."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s = load('overseas-any-file-deploy')
p = load('package-any-file')
baseline = load('test_studio_ux_release')
baseline.d = baseline.t.d = baseline.t.t.d = s.d
baseline.t.p = s.d.proxy
baseline.a = s.a.a
OWNER = '11111111-1111-4111-8111-111111111111'


class AnyFileReleaseTests(baseline.StudioUXReleaseTests):
    def test_prepared_overlay_allows_only_api_image_build(self):
        # Exercise the inherited exact Compose comparison independently of our new pin.
        self.mock(s.d, 'prepared_settings', new=s._prepared_settings)
        super().test_prepared_overlay_allows_only_api_image_build()

    def test_owner_drift_aborts_before_closing_intake(self):
        work, _, events = self.setup_deploy()
        private(work / 'any-file-baseline.private.json', {'owner': OWNER, 'schema': 'original'})
        self.mock(s, 'owner_binding', return_value='changed')
        s.d.prepared_settings.side_effect = s.prepared_settings
        with self.assertRaisesRegex(AssertionError, 'owner binding drift'):
            self.deploy(work)
        assert not (work / 'DEPLOY_STARTED').exists()
        assert not any(row[0] in ('close', 'drain', 'backup', 'switch', 'open') for row in events)


def private(path, value):
    path.write_text(value if isinstance(value, str) else json.dumps(value))


def test_baseline_and_no_migration_hooks():
    assert (s.a.BASE_VERSION, s.d.TARGET_VERSION, p.p.VERSION) == ('0.2.47', '0.2.48', '0.2.48')
    assert s.FRONTEND_RELEASE == s.a.BASE_RELEASE == 'overseas-20261022-5c3715f'
    assert s.a.BASE_IMAGE == 'sha256:ed7bafd1e6c0008fb89d7f19ef23e24546f5bcf2819b34de1b7aebb39924935c'
    assert s.d.DOMESTIC_MIGRATION == p.p.DOMESTIC_MIGRATION == '0032'
    assert s.d.TARGET_MIGRATION == p.p.OVERSEAS_MIGRATION == 'overseas_0020'
    assert all('domestic-retention-20261021-bec8dd7' in str(v) for v in s.a.DOMESTIC_PATHS.values())
    assert all(s.a.BASE_RELEASE in str(v) for v in s.a.OVERSEAS_PATHS.values())
    assert str(s.a.DOMESTIC_AUTH).replace('\\', '/').endswith('domestic-codex-auth-20261019/backend')
    assert s.d.before_switch is s.verify_unchanged_data
    assert s.d.prepare is s.prepare and s.d.installed is s.installed
    assert s.a.schemas is s.d.schemas is s.d.installed_schemas is s.schemas
    assert s.u.DROP > 'zzzzzzz-skill-availability-20261022.conf'
    assert 'environment' not in s.d.resources.overlay('/source', 'image')['services']['api']


@pytest.mark.parametrize('fault', [None, 'domestic', 'revision', 'usage', 'visibility', 'audit', 'deletion', 'availability'])
def test_schema_checks_existing_tables_only(monkeypatch, fault):
    monkeypatch.setattr(s.d.r, 'sql', lambda _: '0030' if fault == 'domestic' else '0032')
    values = ['wrong' if fault == 'revision' else 'overseas_0020', '1' if fault == 'usage' else '0']
    values += ['0' if fault == name else '1' for name in ('visibility', 'audit', 'deletion', 'availability')]
    sql = Mock(side_effect=values)
    monkeypatch.setattr(s.u, 'sql', sql)
    if fault:
        with pytest.raises(AssertionError): s.schemas()
    else:
        s.schemas()
        assert len(sql.call_args_list) == 6


@pytest.mark.parametrize('entries', [[], [s.OWNER_KEY + '='], [s.OWNER_KEY + '=invalid'], [s.OWNER_KEY + '=' + OWNER] * 2])
def test_owner_requires_existing_unique_binding(monkeypatch, entries):
    monkeypatch.setattr(s.m, 'live', lambda _: {'Config': {'Env': entries}})
    with pytest.raises((AssertionError, ValueError)): s.owner_binding()


@pytest.mark.parametrize('fault', [None, 'owner', 'schema', 'compose'])
def test_prepared_settings_preserve_exact_existing_owner(tmp_path, monkeypatch, fault):
    private(tmp_path / 'any-file-baseline.private.json', {'owner': OWNER, 'schema': 'original'})
    private(tmp_path / 'overseas-compose.private.json', {'services': {'api': {'environment': {
        s.OWNER_KEY: 'other' if fault == 'compose' else OWNER}}}})
    monkeypatch.setattr(s, 'owner_binding', lambda: 'other' if fault == 'owner' else OWNER)
    monkeypatch.setattr(s.u, 'sql', lambda _: 'changed' if fault == 'schema' else 'original')
    check = Mock()
    monkeypatch.setattr(s, '_prepared_settings', check)
    if fault:
        with pytest.raises(AssertionError): s.prepared_settings(tmp_path, {}, 'image', tmp_path / 'src')
        check.assert_not_called()
    else:
        s.prepared_settings(tmp_path, {}, 'image', tmp_path / 'src')
        check.assert_called_once()


def test_compose_overlay_preserves_all_environment_and_owner():
    before = {'services': {'api': {'image': 'old', 'restart': 'unless-stopped',
        'mem_limit': s.d.resources.API_MEMORY, 'environment': {s.OWNER_KEY: OWNER, 'UNCHANGED': 'yes'}},
        'redis': {'image': 'redis'}}}
    after = copy.deepcopy(before)
    after['services']['api'].update(s.d.resources.overlay('/source', 'tested')['services']['api'])
    s.d.resources.same_settings(before, after, s.m)
    for key in (s.OWNER_KEY, 'UNCHANGED'):
        broken = copy.deepcopy(after)
        broken['services']['api']['environment'][key] = 'changed'
        with pytest.raises(AssertionError): s.d.resources.same_settings(before, broken, s.m)


@pytest.mark.parametrize('retry_drift', [False, True])
def test_prepare_pins_existing_values_without_owner_file(tmp_path, monkeypatch, retry_drift):
    source = tmp_path / 'src'; source.mkdir()
    monkeypatch.setattr(s, 'schemas', Mock())
    monkeypatch.setattr(s.a, 'preflight', Mock())
    monkeypatch.setattr(s, 'owner_binding', lambda: OWNER)
    monkeypatch.setattr(s.u, 'sql', lambda _: 'original')
    monkeypatch.setattr(s.m, 'private', private)
    prepare = Mock()
    monkeypatch.setattr(s, '_prepare', prepare)
    if retry_drift:
        private(tmp_path / 'any-file-baseline.private.json', {'owner': OWNER, 'schema': 'changed'})
        with pytest.raises(AssertionError, match='Baseline drift'): s.prepare(tmp_path, source, {}, 'image')
        prepare.assert_not_called()
    else:
        s.prepare(tmp_path, source, {}, 'image')
        assert json.loads((tmp_path / 'any-file-baseline.private.json').read_text()) == {'owner': OWNER, 'schema': 'original'}
        assert not (tmp_path / 'skill-owner.env').exists()
        prepare.assert_called_once_with(tmp_path, source, {}, 'image')


@pytest.mark.parametrize('fault', [None, 'backup', 'drain', 'schema', 'settings', 'rows', 'missing-table'])
def test_no_migration_requires_exact_backup_rows(tmp_path, monkeypatch, fault):
    work, backup = tmp_path / 'work', tmp_path / 'backup'
    work.mkdir(); backup.mkdir()
    if fault != 'backup': (backup / 'COMPLETE').touch()
    if fault != 'drain': (work / 'EXECUTORS_STOPPED').touch()
    before = {'archives': 'original', s.TABLE: '3:arbitrary-disabled-version-9'}
    if fault == 'missing-table': before.pop(s.TABLE)
    private(backup / 'fingerprints.json', before)
    monkeypatch.setattr(s, 'schemas', Mock(side_effect=AssertionError('schema') if fault == 'schema' else None))
    monkeypatch.setattr(s, 'prepared_settings', Mock(side_effect=AssertionError('settings') if fault == 'settings' else None))
    monkeypatch.setattr(s.a.a, 'fingerprint', lambda _: {} if fault == 'rows' else before)
    compose, run = Mock(), Mock()
    monkeypatch.setattr(s.m, 'compose', compose)
    monkeypatch.setattr(s.m, 'run', run)
    monkeypatch.setattr(s.m, 'private', private)
    if fault:
        with pytest.raises(AssertionError): s.verify_unchanged_data(work, tmp_path, 'image', {}, backup)
        assert not (work / 'SCHEMA_UNCHANGED').exists()
    else:
        s.verify_unchanged_data(work, tmp_path, 'image', {}, backup)
        assert (work / 'SCHEMA_UNCHANGED').exists()
        assert json.loads((work / 'skill-state.private.json').read_text())['fingerprint'] == before[s.TABLE]
    compose.assert_not_called()
    run.assert_not_called()
    assert not (work / 'MIGRATION_STARTED').exists()


@pytest.mark.parametrize('fault', [None, 'owner', 'schema', 'states'])
def test_installed_preserves_arbitrary_skill_states(tmp_path, monkeypatch, fault):
    private(tmp_path / 'any-file-baseline.private.json', {'owner': OWNER, 'schema': 'original'})
    private(tmp_path / 'skill-state.private.json', {'fingerprint': '7:disabled-and-custom-versions'})
    monkeypatch.setattr(s, '_installed', Mock())
    monkeypatch.setattr(s, 'owner_binding', lambda: 'changed' if fault == 'owner' else OWNER)
    monkeypatch.setattr(s.u, 'sql', lambda _: 'changed' if fault == 'schema' else 'original')
    monkeypatch.setattr(s.a.a, 'fingerprint', lambda _: {s.TABLE: 'changed' if fault == 'states' else '7:disabled-and-custom-versions'})
    monkeypatch.setattr(s.m, 'private', private)
    if fault:
        with pytest.raises(AssertionError): s.installed(tmp_path, {}, 'image', {}, {}, tmp_path)
        assert not (tmp_path / 'ANY_FILE_PRESERVATION_VERIFIED').exists()
    else:
        s.installed(tmp_path, {}, 'image', {}, {}, tmp_path)
        assert (tmp_path / 'ANY_FILE_PRESERVATION_VERIFIED').exists()


@pytest.mark.parametrize('fault', [None, 'image', 'group', 'env', 'override', 'loaded-override', 'frontend', 'overseas', 'version', 'memory', 'restart'])
def test_preflight_rejects_baseline_drift(tmp_path, monkeypatch, fault):
    app, systemd = tmp_path / 'app', tmp_path / 'systemd'
    (app / 'frontend').mkdir(parents=True)
    systemd.mkdir()
    private(app / 'frontend/package.json', {'version': 'bad' if fault == 'version' else '0.2.47'})
    for filename, label in [('FRONTEND_RELEASE.json', 'frontend'), ('OVERSEAS_RELEASE.json', 'overseas')]:
        private(app / filename, {'release': 'wrong' if fault == label else s.a.BASE_RELEASE})
    monkeypatch.setattr(s.m, 'APP', app)
    monkeypatch.setattr(s.a.c, 'SYSTEMD', systemd)
    monkeypatch.setattr(s.m, 'live', lambda _: {'Image': 'bad' if fault == 'image' else s.a.BASE_IMAGE,
        'State': {'Running': True, 'Health': {'Status': 'healthy'}},
        'HostConfig': {'Memory': 0 if fault == 'memory' else s.d.resources.API_MEMORY,
                       'RestartPolicy': {'Name': 'no' if fault == 'restart' else 'unless-stopped'}}})
    for name in ('native_state', 'domestic_native', 'pointer'): monkeypatch.setattr(s.a, name, Mock())
    monkeypatch.setattr(s.a, 'settings', lambda _: {'SupplementaryGroups': '' if fault == 'group' else 'hengxin-codex-auth',
        'Environment': '' if fault == 'env' else 'OVERSEAS_CODEX_AUTH_BROKER_SOCKET=' + str(s.a.SOCKET)})
    monkeypatch.setattr(s.a, 'show', lambda *_: '/unit/zzzzzzzzz-other.conf' if fault == 'loaded-override' else '/unit/zzzzzzz-skill-availability-20261022.conf')
    for unit in s.u.UNITS:
        folder = systemd / (unit + '.service.d'); folder.mkdir()
        if fault == 'override': (folder / 'zzzzzzzzz-other.conf').touch()
    edge = tmp_path / 'edge'; edge.write_text('safe proxy')
    monkeypatch.setattr(s.m, 'EDGE', edge)
    monkeypatch.setattr(s.d.proxy, 'inner', lambda _: edge)
    monkeypatch.setattr(s.a.c.a, 'proxy_baseline', Mock())
    if fault:
        with pytest.raises(AssertionError): s.a.preflight()
    else:
        s.a.preflight()
        s.a.domestic_native.assert_called_once()


def test_package_contract_and_runtime_dependency_closure():
    files = dict.fromkeys(p.REQUIRED, b'')
    files.update({'frontend/package.json': b'{"version":"0.2.48"}',
        'frontend/dist/index.html': b'<script src="/assets/main.js"></script>', 'frontend/dist/assets/main.js': b'console.log(1)'})
    p.validate(files)
    for name in p.REQUIRED:
        assert name.startswith('frontend/dist/') or p.selected(name if name.startswith('scripts/') else p.p.APP + name) == name
        with pytest.raises(ValueError, match='Missing'): p.validate({k: v for k, v in files.items() if k != name})
    seen, pending = set(), ['overseas-any-file-deploy.py', 'release-retention.py']
    while pending:
        name = pending.pop()
        if name in seen: continue
        seen.add(name)
        assert p.selected('scripts/release/' + name) == 'scripts/release/' + name
        for node in ast.walk(ast.parse(Path(__file__).with_name(name).read_text(encoding='utf-8'))):
            if isinstance(node, ast.Call) and node.args and isinstance(node.func, ast.Attribute):
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if node.func.attr == 'with_name' and arg.value.endswith('.py'): pending.append(arg.value)
                    elif node.func.attr == 'module': pending.append(arg.value + '.py')
    assert 'overseas-skill-availability-deploy.py' not in seen
    assert 'overseas-skill-availability-owner.py' not in seen


def test_actual_package_sources_pass_privacy():
    repo = Path(__file__).resolve().parents[2]
    paths = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=repo, text=True).split('\0')
    for path in paths:
        if name := p.selected(path):
            p.p.m.common.privacy_check(name, p.p.m.common.normalized((repo / path).read_bytes()))
    for name in (*p.p.PACKAGING_HELPERS, 'test_any_file_release.py'):
        assert p.selected('scripts/release/' + name) is None
    assert p.selected('scripts/release/any-file-baseline.private.json') is None


def test_optimized_python_aborts_before_production_actions():
    result = subprocess.run([sys.executable, '-O', str(Path(__file__).with_name('overseas-any-file-deploy.py')),
        'overseas-20261022-abcdef0', 'build'], capture_output=True, text=True,
        env={**os.environ, 'PYTHONOPTIMIZE': '1'}, timeout=30)
    assert result.returncode != 0
    assert 'Python -O disables release safety assertions' in result.stderr
