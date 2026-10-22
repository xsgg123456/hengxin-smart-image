"""Pinned availability deployment fault matrix; all production operations mocked."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

s = load('overseas-skill-availability-deploy')
p = load('package-skill-availability')
baseline = load('test_studio_ux_release')
baseline.d = baseline.t.d = baseline.t.t.d = s.d
baseline.t.p = s.d.proxy
baseline.a = s.a.a
OWNER = '11111111-1111-4111-8111-111111111111'

class SkillAvailabilityReleaseTests(baseline.StudioUXReleaseTests):
    def test_prepared_overlay_allows_only_api_image_build(self):
        self.mock(s.owner, 'pinned', return_value=OWNER)
        super().test_prepared_overlay_allows_only_api_image_build()

    def test_changed_owner_aborts_before_closing_intake(self):
        real_settings = s.d.prepared_settings
        work, _, events = self.setup_deploy()
        private(work / 'skill-owner.private.json', {'owner': OWNER, 'sha256': 'prepared'})
        self.mock(s.owner, 'read', return_value={'owner': OWNER, 'sha256': 'changed'})
        s.d.prepared_settings.side_effect = real_settings
        with self.assertRaisesRegex(AssertionError, 'Owner binding changed'):
            s.d.deploy(work, work / 'src', {'release': 'fixture', 'files': {}}, 'image')
        assert not (work / 'DEPLOY_STARTED').exists()
        assert not any(event[0] in ('close', 'compose', 'drain', 'backup', 'switch', 'open') for event in events)


def private(path, value):
    path.write_text(value if isinstance(value, str) else json.dumps(value))


def test_release_baseline_and_hooks():
    assert (s.a.BASE_VERSION, s.d.TARGET_VERSION, p.p.VERSION) == ('0.2.46', '0.2.47', '0.2.47')
    assert s.FRONTEND_RELEASE == 'domestic-retention-20261021-bec8dd7'
    assert s.a.BASE_RELEASE == 'overseas-20261019-1c28ee2'
    assert s.a.BASE_IMAGE == 'sha256:1a406c0ad954788dbe5b6c004005dcea6005e318995dc716e1d86d3fcc808854'
    assert s.d.DOMESTIC_MIGRATION == p.p.DOMESTIC_MIGRATION == '0032'
    assert s.d.TARGET_MIGRATION == p.p.OVERSEAS_MIGRATION == 'overseas_0020'
    assert p.p.RELEASE_PREFIX == 'overseas-20261022-'
    assert all(s.FRONTEND_RELEASE in str(path) for path in s.a.DOMESTIC_PATHS.values())
    assert all(s.a.BASE_RELEASE in str(path) for path in s.a.OVERSEAS_PATHS.values())
    assert s.a.DOMESTIC_AUTH.as_posix().endswith('domestic-codex-auth-20261019/backend')
    assert s.a.preflight is s.d.preflight is s.preflight
    assert s.a.schemas is s.d.schemas is s.schemas
    assert s.d.before_switch is s.migrate
    assert s.d.domestic_native is s.a.domestic_native
    assert s.u.DROP > 'zzzzzz-studio-reopen-20261019.conf'


@pytest.mark.parametrize('fault', [None, 'domestic', 'revision', 'usage', 'visibility', 'audit', 'deletion', 'availability'])
def test_schema_checks_preserve_real_baseline(monkeypatch, fault):
    monkeypatch.setattr(s.d.r, 'sql', lambda _: '0030' if fault == 'domestic' else '0032')
    values = ['wrong' if fault == 'revision' else 'overseas_0019', '1' if fault == 'usage' else '0']
    values += ['0' if fault == name else '1' for name in ('visibility', 'audit', 'deletion')]
    values += ['1' if fault == 'availability' else '0']
    monkeypatch.setattr(s.u, 'sql', Mock(side_effect=values))
    if fault:
        with pytest.raises(AssertionError): s.schemas()
    else:
        s.schemas()


@pytest.mark.parametrize('rows,count', [('', '0'), ('other', '2'), ('amazon-new-product-image-set\namazon-new-product-aplus', '3')])
def test_initial_seeds_reject_missing_or_extra(monkeypatch, rows, count):
    monkeypatch.setattr(s, 'check_schema', Mock())
    monkeypatch.setattr(s.u, 'sql', Mock(side_effect=[rows, count]))
    with pytest.raises(AssertionError): s.installed_schemas()


@pytest.mark.parametrize('fault', [None, 'missing', 'mode', 'uid', 'symlink', 'blank', 'extra', 'duplicate', 'uuid'])
def test_owner_binding_is_private_and_exact(tmp_path, monkeypatch, fault):
    path = tmp_path / 'skill-owner.env'
    raw = s.owner.KEY + '=' + OWNER + '\n'
    if fault == 'blank': raw += '\n'
    if fault == 'extra': raw += 'OTHER=value\n'
    if fault == 'duplicate': raw += raw
    if fault == 'uuid': raw = s.owner.KEY + '=not-a-uuid\n'
    if fault != 'missing': path.write_text(raw)
    original = Path.lstat
    def metadata(candidate):
        if candidate != path: return original(candidate)
        if not path.exists(): raise FileNotFoundError(path)
        return SimpleNamespace(st_mode=(stat.S_IFLNK if fault == 'symlink' else stat.S_IFREG) | (0o644 if fault == 'mode' else 0o600),
                               st_uid=1000 if fault == 'uid' else 0, st_gid=0)
    monkeypatch.setattr(Path, 'lstat', metadata)
    if fault:
        with pytest.raises((AssertionError, FileNotFoundError)): s.owner.read(tmp_path)
    else:
        assert s.owner.read(tmp_path)['owner'] == OWNER


@pytest.mark.parametrize('fault', [None, 'digest', 'owner', 'inactive', 'missing'])
def test_owner_is_pinned_across_prepare_and_deploy(tmp_path, monkeypatch, fault):
    binding = {'owner': OWNER, 'sha256': 'fixed'}
    private(tmp_path / 'skill-owner.private.json', binding)
    current = dict(binding)
    if fault == 'digest': current['sha256'] = 'drift'
    if fault == 'owner': current['owner'] = '22222222-2222-4222-8222-222222222222'
    monkeypatch.setattr(s.owner, 'read', Mock(side_effect=FileNotFoundError() if fault == 'missing' else None, return_value=current))
    sql = Mock(return_value='0' if fault == 'inactive' else '1')
    monkeypatch.setattr(s.u, 'sql', sql)
    if fault:
        with pytest.raises((AssertionError, FileNotFoundError)): s.owner.pinned(tmp_path, s.u)
    else:
        assert s.owner.pinned(tmp_path, s.u) == OWNER
        assert "status='active'" in sql.call_args.args[0] and "role='super_admin'" in sql.call_args.args[0]


def test_prepare_integrates_pinned_owner_and_native_baselines(tmp_path, monkeypatch):
    work = tmp_path / 'work'; work.mkdir()
    source = work / 'src'; source.mkdir()
    private(work / 'UPLOAD_CAPACITY_IMAGE_ID', 'tested')
    (tmp_path / 'frontend').mkdir()
    private(tmp_path / 'frontend/package.json', {'version': '0.2.46'})
    binding = {'owner': OWNER, 'sha256': 'fixed'}
    data = {'overseas': {'env': '/env'}, 'native': {k: str(v) for k, v in s.a.OVERSEAS_PATHS.items()}}
    monkeypatch.setattr(s.owner, 'read', lambda _: binding)
    monkeypatch.setattr(s.u, 'sql', Mock(return_value='1'))
    monkeypatch.setattr(s.m, 'APP', tmp_path)
    monkeypatch.setattr(s.m, 'image_id', lambda *_: 'tested')
    monkeypatch.setattr(s.m, 'topology', lambda: data)
    monkeypatch.setattr(s.m, 'GROUPS', ())
    monkeypatch.setattr(s.m, 'private', private)
    for module, name in [(s.a, 'schemas'), (s.a, 'preflight'), (s.m, 'assets_safe'), (s.d.drain, 'idle'),
                         (s.d, 'prepared_settings'), (s.d.r, 'hashes'), (s.m.skills, 'verify'), (s.d.proxy, 'prepare')]:
        monkeypatch.setattr(module, name, Mock())
    monkeypatch.setattr(s.a, 'domestic_native', lambda: {'broker': 'unchanged'})
    monkeypatch.setattr(s.a, 'settings', lambda _: {'group': 'auth'})
    monkeypatch.setattr(s.d, 'evidence', lambda _: {'workers': {}})
    monkeypatch.setattr(s.u, 'prepare_native', lambda *_: tmp_path / 'new/backend')
    s.prepare(work, source, {'release': 'new', 'files': {}}, 'image')
    assert (work / 'PREPARED').read_text() == 'tested'
    assert json.loads((work / 'skill-owner.private.json').read_text()) == binding
    assert json.loads((work / 'overseas-overlay.json').read_text())['services']['api']['environment'] == {s.owner.KEY: OWNER}
    assert json.loads((work / 'overseas-native-settings.json').read_text()) == {unit: {'group': 'auth'} for unit in s.u.UNITS}


@pytest.mark.parametrize('fault', [None, 'missing', 'otherenv', 'mount', 'other-service', 'restart', 'memory'])
def test_only_exact_api_owner_environment_delta_is_allowed(fault):
    before = {'services': {'api': {'image': 'old', 'environment': {'SAFE': 'yes'}, 'volumes': ['/safe']},
                           'migrate': {'image': 'old', 'environment': {'SAFE': 'yes'}}}}
    after = copy.deepcopy(before)
    after['services']['api'].update(image='new', mem_limit=s.d.resources.API_MEMORY, restart='unless-stopped')
    after['services']['api']['environment'][s.owner.KEY] = OWNER
    if fault == 'missing': after['services']['api']['environment'].pop(s.owner.KEY)
    if fault == 'otherenv': after['services']['api']['environment']['SAFE'] = 'changed'
    if fault == 'mount': after['services']['api']['volumes'] = ['/other']
    if fault == 'other-service': after['services']['migrate']['environment'][s.owner.KEY] = OWNER
    if fault == 'restart': after['services']['api']['restart'] = 'no'
    if fault == 'memory': after['services']['api']['mem_limit'] = 1
    if fault:
        with pytest.raises((AssertionError, ValueError)): s.same_settings(before, after, s.m)
    else:
        s.same_settings(before, after, s.m)
        assert s.owner.KEY in after['services']['api']['environment']


@pytest.mark.parametrize('fault', [None, 'backup', 'drain', 'schema', 'pre-rows', 'config', 'migration', 'rows', 'extra', 'missing', 'owner', 'columns'])
def test_additive_migration_and_failure_closure(tmp_path, monkeypatch, fault):
    work, backup = tmp_path / 'work', tmp_path / 'backup'
    work.mkdir(); backup.mkdir()
    if fault != 'backup': (backup / 'COMPLETE').touch()
    if fault != 'drain': (work / 'EXECUTORS_STOPPED').touch()
    private(backup / 'fingerprints.json', {'archives': 'original'})
    before = {'services': {'migrate': {'image': 'old', 'environment': {'SAFE': 'yes'}}, 'api': {'image': 'old'}}}
    private(work / 'overseas-compose.private.json', before)
    after = copy.deepcopy(before)
    after['services']['migrate']['image'] = 'tested'
    if fault == 'config': after['services']['api']['image'] = 'changed'
    rows = {'archives': 'changed' if fault == 'rows' else 'original', s.TABLE: '2:seeds'}
    if fault == 'extra': rows['unexpected'] = '0:empty'
    if fault == 'missing': rows.pop('archives')
    monkeypatch.setattr(s.owner, 'pinned', Mock(side_effect=AssertionError('owner') if fault == 'owner' else None))
    monkeypatch.setattr(s, 'schemas', Mock(side_effect=AssertionError('schema') if fault == 'schema' else None))
    monkeypatch.setattr(s, 'installed_schemas', Mock())
    monkeypatch.setattr(s.u, 'sql', Mock(side_effect=['original-columns', 'changed' if fault == 'columns' else 'original-columns']))
    monkeypatch.setattr(s.a.a, 'fingerprint', Mock(side_effect=[{'archives': 'changed' if fault == 'pre-rows' else 'original'}, rows]))
    compose = Mock(side_effect=[json.dumps(before), json.dumps(after), RuntimeError('migration') if fault == 'migration' else ''])
    monkeypatch.setattr(s.m, 'compose', compose)
    monkeypatch.setattr(s.m, 'private', private)
    if fault:
        with pytest.raises((AssertionError, RuntimeError)): s.migrate(work, tmp_path, 'tested', {'overseas': {}}, backup)
        assert not (work / 'MIGRATION_VERIFIED').exists()
        if fault in ('owner', 'backup', 'drain', 'schema', 'pre-rows', 'config'):
            assert not (work / 'MIGRATION_STARTED').exists()
    else:
        s.migrate(work, tmp_path, 'tested', {'overseas': {}}, backup)
        assert compose.call_args.args[-1] == 'overseas_0020'
        assert 'overseas_0020' in (work / 'MIGRATION_VERIFIED').read_text()


@pytest.mark.parametrize('fault', [None, 'image', 'group', 'env', 'override', 'frontend', 'overseas', 'version', 'memory', 'restart'])
def test_preflight_pins_split_releases_and_preserves_broker(tmp_path, monkeypatch, fault):
    app, systemd = tmp_path / 'app', tmp_path / 'systemd'
    (app / 'frontend').mkdir(parents=True)
    systemd.mkdir()
    private(app / 'frontend/package.json', {'version': 'bad' if fault == 'version' else '0.2.46'})
    for filename, release, label in [('FRONTEND_RELEASE.json', s.FRONTEND_RELEASE, 'frontend'),
                                     ('OVERSEAS_RELEASE.json', s.a.BASE_RELEASE, 'overseas')]:
        private(app / filename, {'release': 'wrong' if fault == label else release})
    monkeypatch.setattr(s.m, 'APP', app)
    monkeypatch.setattr(s.a.c, 'SYSTEMD', systemd)
    monkeypatch.setattr(s.m, 'live', lambda _: {'Image': 'bad' if fault == 'image' else s.a.BASE_IMAGE,
        'State': {'Running': True, 'Health': {'Status': 'healthy'}},
        'HostConfig': {'Memory': 0 if fault == 'memory' else s.d.resources.API_MEMORY,
                       'RestartPolicy': {'Name': 'no' if fault == 'restart' else 'unless-stopped'}}})
    for name in ('native_state', 'domestic_native', 'pointer'): monkeypatch.setattr(s.a, name, Mock())
    monkeypatch.setattr(s.a, 'settings', lambda _: {'SupplementaryGroups': '' if fault == 'group' else 'hengxin-codex-auth',
        'Environment': '' if fault == 'env' else 'OVERSEAS_CODEX_AUTH_BROKER_SOCKET=' + str(s.a.SOCKET)})
    monkeypatch.setattr(s.a, 'show', lambda *_: '/unit/zzzz-codex-auth-20261019.conf')
    for unit in s.u.UNITS:
        folder = systemd / (unit + '.service.d'); folder.mkdir()
        if fault == 'override': (folder / 'zzzzzzzz-other.conf').touch()
    edge = tmp_path / 'edge'; edge.write_text('safe proxy')
    monkeypatch.setattr(s.m, 'EDGE', edge)
    monkeypatch.setattr(s.d.proxy, 'inner', lambda _: edge)
    monkeypatch.setattr(s.a.c.a, 'proxy_baseline', Mock())
    if fault:
        with pytest.raises(AssertionError): s.preflight()
    else:
        s.preflight()
        s.a.domestic_native.assert_called_once()


@pytest.mark.parametrize('fault', [None, 'env', 'probe'])
def test_installed_owner_and_catalog_verification_is_required(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(s.owner, 'pinned', lambda *_: OWNER)
    monkeypatch.setattr(s.m, 'live', lambda _: {'Config': {'Env': [] if fault == 'env' else [s.owner.KEY + '=' + OWNER]}})
    monkeypatch.setattr(s.m, 'run', Mock(side_effect=RuntimeError('probe') if fault == 'probe' else None,
        return_value=json.dumps({'ownerVerified': True, 'initialSkillsVerified': True, 'readOnly': True})))
    monkeypatch.setattr(s.m, 'private', private)
    if fault:
        with pytest.raises((AssertionError, RuntimeError)): s.owner.installed(tmp_path, s.m, s.u)
        assert not (tmp_path / 'SKILL_AVAILABILITY_VERIFIED.json').exists()
    else:
        s.owner.installed(tmp_path, s.m, s.u)
        assert 'SET TRANSACTION READ ONLY' in s.m.run.call_args.args[-1]
        assert (tmp_path / 'SKILL_AVAILABILITY_VERIFIED.json').exists()


def test_package_contract_and_chain():
    files = dict.fromkeys(p.REQUIRED, b'')
    files.update({'frontend/package.json': b'{"version":"0.2.47"}',
        'frontend/dist/index.html': b'<script src="/assets/main.js"></script>', 'frontend/dist/assets/main.js': b'console.log(1)'})
    p.validate(files)
    for name in p.REQUIRED:
        assert name.startswith('frontend/dist/') or p.selected(name if name.startswith('scripts/') else p.p.APP + name) == name
        with pytest.raises(ValueError, match='Missing'): p.validate({k: v for k, v in files.items() if k != name})
    assert p.selected('hengxin-smart-image/frontend/preview-studio-reopen/App.vue') is None
    assert p.selected('skill-owner.env') is None
    assert p.selected('scripts/release/skill-owner.private.json') is None
    seen, pending = set(), ['overseas-skill-availability-deploy.py', 'release-retention.py']
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
    assert 'overseas-skill-availability-owner.py' in seen


def test_optimized_python_aborts_before_production_actions():
    result = subprocess.run([sys.executable, '-O', str(Path(__file__).with_name('overseas-skill-availability-deploy.py')),
        'overseas-20261022-abcdef0', 'build'], capture_output=True, text=True,
        env={**os.environ, 'PYTHONOPTIMIZE': '1'}, timeout=30)
    assert result.returncode != 0
    assert 'Python -O disables release safety assertions' in result.stderr


def test_actual_package_sources_pass_privacy_without_local_packaging_tools():
    repo = Path(__file__).resolve().parents[2]
    paths = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=repo, text=True).split('\0')
    for path in paths:
        if name := p.selected(path):
            p.p.m.common.privacy_check(name, p.p.m.common.normalized((repo / path).read_bytes()))
    for name in (*p.p.PACKAGING_HELPERS, 'test_skill_availability_release.py', 'test_studio_ux_release.py'):
        assert p.selected('scripts/release/' + name) is None
