"""Offline image-release manifest, baseline, no-migration and failure tests."""
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
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


c = load('overseas-images-deploy')
d = c.d
t = load('test_overseas_upload')
t.d = t.t.d = d
t.p = d.proxy


class ImagesReleaseTests(t.UploadReleaseTests):
    def test_closed_waits_for_reload_and_times_out_if_still_open(self):
        probe = self.mock(d.m, 'run', side_effect=['401'] * 4 + ['503'] * 4)
        self.mock(c.time, 'sleep')
        d.closed()
        assert probe.call_count == 8
        with pytest.raises(AssertionError, match='did not reach'):
            d.closed(timeout=0)

    def setup_deploy(self, failure=None):
        work, data, events = super().setup_deploy(failure)
        self.mock(d, 'preflight')
        self.mock(d, 'before_switch')
        return work, data, events

    def test_schema_record_and_no_recovery(self):
        work, _, events = self.setup_deploy()
        d.before_switch.side_effect = lambda *args: events.append(('schema-check',))
        self.deploy(work)
        names = [event[0] for event in events]
        assert names.index('backup') < names.index('schema-check') < names.index('switch')
        report = json.loads((work / 'verification.json').read_text())
        assert (report['migration'], report['overseasMigration']) == ('0029', 'overseas_0016')
        assert 'no database migration or context restoration' in (work / 'RECOVERY.txt').read_text()
        assert not (work / 'CONTEXT_RECOVERY_VERIFIED').exists()

    def test_preflight_drift_prevents_mutation(self):
        work, _, events = self.setup_deploy()
        d.preflight.side_effect = AssertionError('baseline drift')
        with pytest.raises(AssertionError): self.deploy(work)
        assert events == []
        assert not (work / 'DEPLOY_STARTED').exists()

    def test_before_switch_failure_stops_cutover(self):
        work, _, events = self.setup_deploy()
        d.before_switch.side_effect = AssertionError('schema drift')
        with pytest.raises(AssertionError): self.deploy(work)
        assert not any(e[0] in ('switch', 'installed', 'open') for e in events)
        assert json.loads((work / 'FAILURE.json').read_text())['phase'] == 'migration'

    def test_optimized_python_aborts_before_production_actions(self):
        for flags, optimize in ((['-O'], '0'), ([], '1')):
            result = subprocess.run([sys.executable, *flags, c.__file__,
                'overseas-20261016-abcdef0', 'build'], capture_output=True, text=True,
                env={**os.environ, 'PYTHONOPTIMIZE': optimize}, timeout=30)
            assert result.returncode != 0
            assert 'Python -O disables release safety assertions' in result.stderr


t.t.HotfixTests = ImagesReleaseTests


@pytest.fixture
def baseline(monkeypatch, tmp_path):
    (tmp_path / 'frontend').mkdir()
    (tmp_path / 'frontend/package.json').write_text(json.dumps({'version': d.BASE_VERSION}))
    for name, release in (('OVERSEAS_RELEASE.json', c.BASE_RELEASE), ('FRONTEND_RELEASE.json', c.BASE_FRONTEND_RELEASE)):
        (tmp_path / name).write_text(json.dumps({'release': release}))
    monkeypatch.setattr(d.m, 'APP', tmp_path)
    monkeypatch.setattr(c, 'SYSTEMD', tmp_path / 'systemd')
    monkeypatch.setattr(d.m, 'EDGE', tmp_path / 'edge.conf')
    (tmp_path / 'infra').mkdir()
    body = 'location ^~ /api/overseas/v1/ { proxy_pass http://upstream;\n' + ''.join(
        f'{key} {value};\n' for key, value in d.proxy.DIRECTIVES.items()) + '}'
    d.m.EDGE.write_text(body)
    d.proxy.inner(d.m).write_text(body)
    units = (*d.u.UNITS, d.m.UNITS[0], c.DELETION_UNIT)
    targets = {unit: c.BASE_NATIVE if unit in d.u.UNITS else c.DOMESTIC_NATIVE for unit in units}
    for unit in units:
        folder = c.SYSTEMD / (unit + '.service.d'); folder.mkdir(parents=True)
        (c.SYSTEMD / (unit + '.service')).write_text('base service')
        (folder / d.u.DROP).write_text(c.a.native_pointer(targets[unit], unit))

    def run(*args, **kwargs):
        if args[1] == 'is-active': return 'active'
        unit, key = args[2], args[4]
        if key == 'WorkingDirectory': return str(targets[unit])
        if key == 'MainPID': return str(units.index(unit) + 100)
        if key == 'User': return 'hengxin-overseas' if unit in d.u.UNITS else 'codex'
        if key == 'FragmentPath': return str(c.SYSTEMD / (unit + '.service'))
        if key == 'DropInPaths': return ' '.join(str(p) for p in sorted((c.SYSTEMD / (unit + '.service.d')).glob('*.conf')))
        if key in ('EnvironmentFiles', 'ExecStart'): return ''
        pytest.fail(repr(args))

    monkeypatch.setattr(d.m, 'run', run)
    monkeypatch.setattr(c.os, 'readlink', lambda path: str(targets[units[int(path.split('/')[2]) - 100]]))
    monkeypatch.setattr(d.m, 'live', Mock(return_value={
        'State': {'Running': True, 'Health': {'Status': 'healthy'}},
        'HostConfig': {'Memory': d.resources.API_MEMORY}}))
    return tmp_path


@pytest.mark.parametrize('fault', ['version', 'release', 'frontend', 'memory', 'health', 'pointer', 'priority',
    'vendor-priority', 'unloaded', 'native-release', 'process-cwd', 'process-zero', 'inactive', 'edge', 'inner', 'user', 'deletion'])
def test_preflight_rejects_drift(baseline, monkeypatch, fault):
    c.preflight()
    folder = c.SYSTEMD / (d.u.UNITS[0] + '.service.d')
    original = d.m.run
    if fault == 'version': (baseline / 'frontend/package.json').write_text('{"version":"0.2.36"}')
    elif fault in ('release', 'frontend'):
        (baseline / ('OVERSEAS_RELEASE.json' if fault == 'release' else 'FRONTEND_RELEASE.json')).write_text('{"release":"unexpected"}')
    elif fault == 'memory': d.m.live.return_value['HostConfig']['Memory'] = 384 * 1024 ** 2
    elif fault == 'health': d.m.live.return_value['State']['Health']['Status'] = 'unhealthy'
    elif fault == 'pointer': (folder / d.u.DROP).write_text('stale')
    elif fault == 'priority': (folder / 'zz.conf').write_text('stale')
    elif fault == 'process-cwd': monkeypatch.setattr(c.os, 'readlink', lambda path: '/old/backend')
    elif fault in ('edge', 'inner'):
        path = d.m.EDGE if fault == 'edge' else d.proxy.inner(d.m)
        path.write_text(path.read_text().replace('500065536', '10485760'))
    else:
        vendor = baseline / 'vendor/zz.conf'
        vendor.parent.mkdir(); vendor.write_text('unexpected')
        def run(*args, **kw):
            if args[1] == 'is-active':
                if fault == 'inactive': raise RuntimeError('inactive')
                return original(*args, **kw)
            key = args[4]
            if fault == 'vendor-priority' and key == 'DropInPaths': return original(*args, **kw) + ' ' + str(vendor)
            if fault == 'unloaded' and key == 'DropInPaths': return ''
            if fault == 'native-release' and key == 'WorkingDirectory': return '/old/backend'
            if fault == 'process-zero' and key == 'MainPID': return '0'
            if fault == 'user' and key == 'User': return 'root'
            if fault == 'deletion' and args[2] == c.DELETION_UNIT and key == 'WorkingDirectory': return '/old/backend'
            return original(*args, **kw)
        monkeypatch.setattr(d.m, 'run', run)
    with pytest.raises((AssertionError, RuntimeError)): c.preflight()


def test_domestic_snapshot_captures_deletion_pid_and_config(baseline, monkeypatch):
    before = c.domestic_native()
    assert set(before) == {d.m.UNITS[0], c.DELETION_UNIT}
    (c.SYSTEMD / (c.DELETION_UNIT + '.service')).write_text('changed service')
    assert c.domestic_native() != before
    original = d.m.run
    monkeypatch.setattr(d.m, 'run', lambda *a, **kw: '999' if a[1] == 'show' and a[4] == 'MainPID' else original(*a, **kw))
    monkeypatch.setattr(c.os, 'readlink', lambda path: str(c.DOMESTIC_NATIVE))
    assert c.domestic_native() != before


@pytest.mark.parametrize('domestic,overseas,column', [('0028', 'overseas_0016', '0'), ('0029', 'overseas_0015', '0'), ('0029', 'overseas_0016', '1')])
def test_schema_drift_rejected_read_only(monkeypatch, domestic, overseas, column):
    monkeypatch.setattr(d.r, 'sql', Mock(return_value=domestic))
    monkeypatch.setattr(d.u, 'sql', Mock(side_effect=[overseas, column]))
    with pytest.raises(AssertionError): c.schemas()
    assert all(call.args[0].startswith('SELECT ') for call in d.r.sql.call_args_list + d.u.sql.call_args_list)


def test_before_switch_only_checks_backup_drain_and_schemas(tmp_path, monkeypatch):
    backup = tmp_path / 'backup'; backup.mkdir()
    check = Mock(); monkeypatch.setattr(c, 'schemas', check)
    with pytest.raises(AssertionError): c.before_switch(tmp_path, tmp_path, 'id', {}, backup)
    (backup / 'COMPLETE').write_text('ok')
    with pytest.raises(AssertionError): c.before_switch(tmp_path, tmp_path, 'id', {}, backup)
    (tmp_path / 'EXECUTORS_STOPPED').write_text('ok')
    c.before_switch(tmp_path, tmp_path, 'id', {}, backup)
    check.assert_called_once_with()


def test_manifest_pins_version_and_schemas(tmp_path, monkeypatch):
    source = tmp_path / 'src'; (source / 'frontend').mkdir(parents=True)
    manifest = dict(release='fixture', frontendVersion='0.2.38', migration='0029', overseasMigration='overseas_0016', files=dict.fromkeys(c.REQUIRED, 'hash'))
    (source / 'frontend/package.json').write_text('{"version":"0.2.38"}')
    monkeypatch.setattr(d.r, 'hashes', Mock())
    (source / 'release.json').write_text(json.dumps(manifest))
    assert c.validate(tmp_path, 'fixture')[1] == manifest
    for key, value in [('frontendVersion', '0.2.37'), ('migration', '0028'), ('overseasMigration', 'overseas_0015'), ('files', {})]:
        (source / 'release.json').write_text(json.dumps({**manifest, key: value}))
        with pytest.raises(AssertionError): c.validate(tmp_path, 'fixture')


def test_cli_build_runs_install_tests_before_capacity(monkeypatch):
    monkeypatch.setattr(d.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(d.os, 'umask', Mock())
    monkeypatch.setattr(d, 'validate', Mock(return_value=(Path('/source'), {}, 'image')))
    events = []
    builder = Mock(); builder.build.side_effect = lambda *a: events.append('installation')
    monkeypatch.setattr(d.m, 'module', Mock(return_value=builder))
    monkeypatch.setattr(d.resources, 'test_capacity', lambda *a: events.append('capacity'))
    monkeypatch.setattr(sys, 'argv', ['images', 'overseas-20261016-abcdef0', 'build'])
    c.main(); assert events == ['installation', 'capacity']
    monkeypatch.setattr(sys, 'argv', ['images', 'overseas-20261015-abcdef0', 'build'])
    with pytest.raises(AssertionError): c.main()
    assert "d.m.module('release-retention').managed(main)" in Path(c.__file__).read_text()


def test_edge_wait_handles_async_reload_and_bounded_probes(monkeypatch):
    run = Mock(side_effect=['200', '200', '503', '503'])
    monkeypatch.setattr(d.m, 'run', run)
    monkeypatch.setattr(c.time, 'sleep', Mock())
    c.wait_edge(('/api/overseas/v1/auth/me',), '503')
    assert run.call_count == 4
    assert all(0 < call.kwargs['timeout'] <= 5 for call in run.call_args_list)


@pytest.mark.parametrize('failure', ['old', 'network'])
def test_edge_wait_timeout_blocks_progress(monkeypatch, failure):
    monkeypatch.setattr(c.time, 'monotonic', Mock(side_effect=[0, 0.1, 0.2, 0.3, 0.4, 1.1]))
    monkeypatch.setattr(c.time, 'sleep', Mock())
    run = Mock(return_value='200', side_effect=subprocess.TimeoutExpired('curl', 1) if failure == 'network' else None)
    monkeypatch.setattr(d.m, 'run', run)
    with pytest.raises(AssertionError, match='did not reach'): c.wait_edge(('/route',), '503', timeout=1)


def test_legacy_defaults_unchanged():
    old = load('overseas-upload-deploy')
    assert (old.TARGET_VERSION, old.DOMESTIC_MIGRATION) == ('0.2.33', '0028')
    assert d.before_switch == c.before_switch and d.u.DROP == '99-overseas-upload.conf'


def test_domestic_exec_statistics_reset_preserves_identity(baseline, monkeypatch):
    original = d.m.run
    state = {'stats': 'start_time=[Fri 2026-10-16 08:00:00 UTC] ; stop_time=[n/a] ; pid=3925617 ; code=(null) ; status=0/0'}
    def run(*args, **kwargs):
        if args[1] == 'show' and args[4] == 'ExecStart':
            return '{ path=/bin/python ; argv[]=/bin/python -m app.deletions ; ignore_errors=no ; ' + state['stats'] + ' }'
        return original(*args, **kwargs)
    monkeypatch.setattr(d.m, 'run', run)
    before = c.domestic_native()
    state['stats'] = 'start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0'
    assert c.domestic_native() == before
    assert before[c.DELETION_UNIT]['pid'] > 0


@pytest.mark.parametrize('change', [('path=/bin/python', 'path=/bin/other'),
    ('-m app.deletions', '-m app.unexpected'), ('ignore_errors=no', 'ignore_errors=yes')])
def test_exec_start_identity_changes_are_not_normalized(change):
    raw = '{ path=/bin/python ; argv[]=/bin/python -m app.deletions ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }'
    assert c.normalize_exec_start(raw) != c.normalize_exec_start(raw.replace(*change))
