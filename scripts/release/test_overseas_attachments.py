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
        return work, data, events

    def test_optimized_python_aborts_before_production_actions(self):
        script = Path(__file__).with_name('overseas-attachments-deploy.py')
        for flags, optimize in ((['-O'], '0'), ([], '1')):
            result = subprocess.run([sys.executable, *flags, str(script),
                'overseas-20261014-abcdef0', 'build'], capture_output=True, text=True,
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
    (tmp_path / 'frontend/package.json').write_text('{"version":"0.2.33"}')
    (tmp_path / 'OVERSEAS_RELEASE.json').write_text('{"release":"overseas-20261014-00720c0"}')
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
    assert (d.TARGET_VERSION, d.BASE_VERSION, d.u.DROP) == ('0.2.34', '0.2.33', '99-overseas-upload.conf')
    source = tmp_path / 'src'
    (source / 'frontend').mkdir(parents=True)
    manifest = {'release': 'fixture', 'frontendVersion': '0.2.34', 'migration': '0028', 'overseasMigration': 'overseas_0015'}
    (source / 'release.json').write_text(json.dumps(manifest))
    (source / 'frontend/package.json').write_text('{"version":"0.2.34"}')
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
