"""Attachment cutover regression and read-only production prerequisite fault tests."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

# Load isolated copies: the inherited matrix patches module globals per case.
import importlib.util


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


a = load('overseas-attachments-deploy')
d = a.d
t = load('test_overseas_upload')
t.d = t.t.d = d
t.p = d.proxy


class AttachmentReleaseTests(t.UploadReleaseTests):
    def setup_deploy(self, failure=None):
        work, data, events = super().setup_deploy(failure)
        self.mock(d, 'preflight')
        self.mock(d, 'before_switch')
        return work, data, events

    def test_migration_runs_between_backup_and_switch_and_failure_stays_closed(self):
        work, _, events = self.setup_deploy()
        d.before_switch.side_effect = lambda *args: events.append(('migration',))
        self.deploy(work)
        names = [event[0] for event in events]
        assert names.index('drain') < names.index('backup') < names.index('migration') < names.index('switch')
        assert json.loads((work / 'verification.json').read_text())['overseasMigration'] == 'overseas_0016'
        assert 'never restore old application code' in (work / 'RECOVERY.txt').read_text()

    def test_migration_failure_prevents_switch_and_reopening(self):
        work, _, events = self.setup_deploy()
        d.before_switch.side_effect = RuntimeError('migration failure')
        with pytest.raises(RuntimeError, match='migration failure'):
            self.deploy(work)
        assert json.loads((work / 'FAILURE.json').read_text())['phase'] == 'migration'
        assert not any(event[0] in ('switch', 'installed', 'open') for event in events)
        assert events[-1] == ('compose', 'overseas', 'stop', '-t', '30', 'api')
        assert [event[0] for event in events].count('close') == 2

    def test_optimized_python_aborts_before_production_actions(self):
        script = Path(__file__).with_name('overseas-attachments-deploy.py')
        for flags, optimize in ((['-O'], '0'), ([], '1')):
            result = subprocess.run([sys.executable, *flags, str(script),
                'overseas-20261015-abcdef0', 'build'], capture_output=True, text=True,
                env={**os.environ, 'PYTHONOPTIMIZE': optimize}, timeout=30)
            assert result.returncode != 0
            assert 'Python -O disables release safety assertions' in result.stderr

    def test_preflight_failure_prevents_intake_close_and_backup(self):
        work, _, events = self.setup_deploy()
        d.preflight.side_effect = AssertionError('baseline drift')
        with pytest.raises(AssertionError, match='baseline drift'):
            self.deploy(work)
        assert events == []
        assert not (work / 'DEPLOY_STARTED').exists()


t.t.HotfixTests = AttachmentReleaseTests


@pytest.fixture
def baseline(monkeypatch, tmp_path):
    (tmp_path / 'frontend').mkdir()
    (tmp_path / 'frontend/package.json').write_text('{"version":"0.2.34"}')
    (tmp_path / 'OVERSEAS_RELEASE.json').write_text('{"release":"overseas-20261014-3b09fbc"}')
    monkeypatch.setattr(d.m, 'APP', tmp_path)
    monkeypatch.setattr(a, 'SYSTEMD', tmp_path / 'systemd')
    monkeypatch.setattr(d.m, 'EDGE', tmp_path / 'edge.conf')
    (tmp_path / 'infra').mkdir()
    body = 'location ^~ /api/overseas/v1/ { proxy_pass http://upstream;\n' + ''.join(
        f'{key} {value};\n' for key, value in d.proxy.DIRECTIVES.items()) + '}'
    d.m.EDGE.write_text(body)
    d.proxy.inner(d.m).write_text(body)
    for unit in d.u.UNITS:
        folder = a.SYSTEMD / (unit + '.service.d')
        folder.mkdir(parents=True)
        for name in ('90-overseas-update.conf', '95-codex-astra.conf'):
            (folder / name).write_text('historical baseline')
        (folder / d.u.DROP).write_text(a.native_pointer(Path('/old/backend'), unit))

    def run(*args, **kwargs):
        if args[4] == 'WorkingDirectory':
            return '/old/backend'
        assert args[4] == 'DropInPaths'
        return ' '.join(str(p) for p in sorted((a.SYSTEMD / (args[2] + '.service.d')).glob('*.conf')))

    monkeypatch.setattr(d.m, 'run', run)
    monkeypatch.setattr(d.m, 'live', Mock(return_value={
        'State': {'Running': True, 'Health': {'Status': 'healthy'}},
        'HostConfig': {'Memory': d.resources.API_MEMORY}}))
    return tmp_path


@pytest.mark.parametrize('fault', ['version', 'release', 'memory', 'health', 'pointer', 'priority', 'unloaded', 'proxy', 'duplicate'])
def test_preflight_rejects_configuration_regression(baseline, monkeypatch, fault):
    a.preflight()
    folder = a.SYSTEMD / (d.u.UNITS[0] + '.service.d')
    if fault == 'version':
        (baseline / 'frontend/package.json').write_text('{"version":"0.2.32"}')
    elif fault == 'release':
        (baseline / 'OVERSEAS_RELEASE.json').write_text('{"release":"unexpected"}')
    elif fault == 'memory':
        d.m.live.return_value['HostConfig']['Memory'] = 384 * 1024 ** 2
    elif fault == 'health':
        d.m.live.return_value['State']['Health']['Status'] = 'unhealthy'
    elif fault == 'pointer':
        (folder / d.u.DROP).write_text('stale pointer')
    elif fault == 'priority':
        (folder / 'zz-override.conf').write_text('unexpected')
    elif fault == 'unloaded':
        original = d.m.run
        monkeypatch.setattr(d.m, 'run', lambda *args, **kw: original(*args, **kw) if args[4] == 'WorkingDirectory' else '')
    elif fault == 'proxy':
        d.m.EDGE.write_text(d.m.EDGE.read_text().replace('500065536', '10485760'))
    else:
        d.m.EDGE.write_text(d.m.EDGE.read_text().replace('client_max_body_size', 'client_max_body_size 500065536; client_max_body_size'))
    with pytest.raises(AssertionError):
        a.preflight()


def test_proxy_preparation_preserves_original_and_rejects_package_drift(baseline, monkeypatch):
    monkeypatch.setattr(d.m, 'private', lambda path, body: path.write_text(body))
    work = baseline / 'work'
    work.mkdir()
    include = baseline / 'infra/nginx.overseas-upload.inc'
    include.write_text(''.join(f'{key} {value};\n' for key, value in d.proxy.DIRECTIVES.items()))
    a.prepare_proxy(work, baseline, d.m)
    for label, path in (('edge', d.m.EDGE), ('inner', d.proxy.inner(d.m))):
        assert (work / f'upload-{label}-before.conf').read_bytes() == path.read_bytes()
        assert (work / f'upload-{label}-after.conf').read_bytes() == path.read_bytes()
    include.write_text('client_max_body_size 10m;')
    with pytest.raises(AssertionError, match='directive drift'):
        a.prepare_proxy(work, baseline, d.m)


def test_target_and_legacy_versions_remain_isolated(tmp_path, monkeypatch):
    legacy = load('overseas-upload-deploy')
    assert (legacy.TARGET_VERSION, legacy.BASE_VERSION, legacy.u.DROP) == ('0.2.33', '0.2.32', '90-overseas-update.conf')
    assert (d.TARGET_VERSION, d.BASE_VERSION, d.u.DROP) == ('0.2.35', '0.2.34', '99-overseas-upload.conf')
    source = tmp_path / 'src'
    (source / 'frontend').mkdir(parents=True)
    manifest = {'release': 'fixture', 'frontendVersion': '0.2.35', 'migration': '0028', 'overseasMigration': 'overseas_0016'}
    (source / 'release.json').write_text(json.dumps(manifest))
    (source / 'frontend/package.json').write_text('{"version":"0.2.35"}')
    monkeypatch.setattr(d.r, 'hashes', Mock())
    assert d.validate(tmp_path, 'fixture')[1] == manifest
    with pytest.raises(AssertionError):
        legacy.validate(tmp_path, 'fixture')


def test_switch_updates_only_effective_99_pointer(baseline, monkeypatch):
    originals = {path: path.read_bytes() for path in a.SYSTEMD.rglob('*.conf') if path.name != d.u.DROP}
    monkeypatch.setattr(d.u, 'Path', lambda value: a.SYSTEMD if value == '/etc/systemd/system' else Path(value))
    monkeypatch.setattr(d.u, 'private', lambda path, body: path.write_text(body))
    run = Mock()
    monkeypatch.setattr(d.u, 'run', run)
    target = Path('/new/backend')
    d.u.switch_native(target)
    run.assert_called_once_with('systemctl', 'daemon-reload')
    for unit in d.u.UNITS:
        assert (a.SYSTEMD / (unit + '.service.d') / d.u.DROP).read_text() == a.native_pointer(target, unit)
    assert all(path.read_bytes() == body for path, body in originals.items())


@pytest.mark.parametrize('entry,date', [
    ('overseas-attachments-deploy', '20261015'), ('overseas-upload-deploy', '20261014')])
def test_cli_release_date_is_pinned_per_entry(monkeypatch, entry, date):
    module = load(entry)
    runtime = module.d if entry == 'overseas-attachments-deploy' else module
    monkeypatch.setattr(runtime.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(runtime.os, 'umask', Mock())
    validate = Mock(return_value=(Path('/source'), {}, 'image'))
    prepare = Mock()
    monkeypatch.setattr(runtime, 'validate', validate)
    monkeypatch.setattr(runtime, 'prepare', prepare)
    release = f'overseas-{date}-abcdef0'
    monkeypatch.setattr(sys, 'argv', [entry, release, 'prepare'])
    runtime.main()
    validate.assert_called_once_with(Path('/opt/hengxin-releases') / release, release)
    prepare.assert_called_once()
    validate.reset_mock()
    other = '20261014' if date == '20261015' else '20261015'
    monkeypatch.setattr(sys, 'argv', [entry, f'overseas-{other}-abcdef0', 'prepare'])
    with pytest.raises(AssertionError):
        runtime.main()
    validate.assert_not_called()

@pytest.mark.parametrize('fault', [None, 'backup', 'drain', 'column', 'config', 'migration', 'revision', 'remaining-column'])
def test_migration_guards_and_exact_owner_service(tmp_path, monkeypatch, fault):
    import copy
    work = tmp_path / 'work'; work.mkdir()
    backup = tmp_path / 'backup'; backup.mkdir()
    if fault != 'backup': (backup / 'COMPLETE').write_text('verified')
    if fault != 'drain': (work / 'EXECUTORS_STOPPED').write_text('verified')
    before = {'services': {'migrate': {'image': 'old', 'environment': {'ROLE': 'owner'}},
                            'api': {'image': 'old', 'mem_limit': 3 * 1024 ** 3}}}
    (work / 'overseas-compose.private.json').write_text(json.dumps(before))
    after = copy.deepcopy(before)
    after['services']['migrate']['image'] = 'sha256:tested'
    if fault == 'config': after['services']['migrate']['environment']['ROLE'] = 'wrong'
    monkeypatch.setattr(d, 'schemas', Mock())
    monkeypatch.setattr(d.r, 'sql', Mock(return_value='0028'))
    sql = Mock(side_effect=['0' if fault == 'column' else '1',
                           'overseas_0015' if fault == 'revision' else 'overseas_0016',
                           '1' if fault == 'remaining-column' else '0'])
    monkeypatch.setattr(d.u, 'sql', sql)
    monkeypatch.setattr(d.m, 'private', lambda path, value: path.write_text(
        value if isinstance(value, str) else json.dumps(value)))
    compose = Mock(side_effect=[json.dumps(before), json.dumps(after),
                               RuntimeError('migration failure') if fault == 'migration' else ''])
    monkeypatch.setattr(d.m, 'compose', compose)
    if fault:
        with pytest.raises((AssertionError, RuntimeError)):
            a.migrate(work, tmp_path, 'sha256:tested', {'overseas': {'group': 'overseas'}}, backup)
        assert not (work / 'MIGRATION_VERIFIED').exists()
        if fault in ('backup', 'drain', 'column', 'config'):
            assert not (work / 'MIGRATION_STARTED').exists()
            assert not any('run' in call.args for call in compose.call_args_list)
    else:
        a.migrate(work, tmp_path, 'sha256:tested', {'overseas': {'group': 'overseas'}}, backup)
        assert (work / 'MIGRATION_VERIFIED').read_text() == 'overseas_0016: overseas_jobs.usage absent'
        assert compose.call_args.args[1:] == ('run', '--rm', '--no-deps', '--pull', 'never',
            'migrate', 'alembic', '-c', 'alembic.overseas.ini', 'upgrade', 'overseas_0016')
        overlay = json.loads((work / 'overseas-migration-overlay.json').read_text())
        assert set(overlay['services']) == {'migrate'}
        assert overlay['services']['migrate']['image'] == 'sha256:tested'
