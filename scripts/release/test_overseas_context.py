"""Offline context cutover fault matrix, pinned prerequisites and recovery boundary."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


c = load('overseas-context-deploy')
d = c.d
t = load('test_overseas_upload')
t.d = t.t.d = d
t.p = d.proxy
TARGETS = {'conversationIds': ['0b8feaa4-f302-4cc5-8cec-767004f0086d']}


def targets(work):
    (work / 'context-targets.json').write_text(json.dumps(TARGETS))
    (work / 'CONTEXT_TARGETS_SHA256').write_text(c.target_digest(work))


class ContextReleaseTests(t.UploadReleaseTests):
    def setup_deploy(self, failure=None):
        work, data, events = super().setup_deploy(failure)
        targets(work)
        self.mock(d, 'preflight')
        self.mock(d, 'before_switch')
        return work, data, events

    def test_recovery_runs_between_backup_and_switch_without_migration(self):
        work, _, events = self.setup_deploy()
        d.before_switch.side_effect = lambda *args: events.append(('context-recovery',))
        self.deploy(work)
        names = [event[0] for event in events]
        assert names.index('drain') < names.index('backup') < names.index('context-recovery') < names.index('switch')
        assert json.loads((work / 'verification.json').read_text())['overseasMigration'] == 'overseas_0016'
        assert 'no database migration' in (work / 'RECOVERY.txt').read_text()
        assert not any('migrate' in event for event in events)

    def test_recovery_failure_prevents_switch_and_reopening(self):
        work, _, events = self.setup_deploy()
        d.before_switch.side_effect = RuntimeError('context recovery failure')
        with pytest.raises(RuntimeError, match='context recovery failure'):
            self.deploy(work)
        assert json.loads((work / 'FAILURE.json').read_text())['phase'] == 'migration'
        assert not any(event[0] in ('switch', 'installed', 'open') for event in events)
        assert events[-1] == ('compose', 'overseas', 'stop', '-t', '30', 'api')
        assert [event[0] for event in events].count('close') == 2

    def test_preflight_failure_prevents_intake_close_and_backup(self):
        work, _, events = self.setup_deploy()
        d.preflight.side_effect = AssertionError('baseline drift')
        with pytest.raises(AssertionError, match='baseline drift'):
            self.deploy(work)
        assert events == []
        assert not (work / 'DEPLOY_STARTED').exists()

    def test_changed_targets_prevent_all_cutover_actions(self):
        work, _, events = self.setup_deploy()
        (work / 'context-targets.json').write_text(json.dumps(TARGETS, indent=2))
        with pytest.raises(AssertionError, match='targets changed'):
            self.deploy(work)
        assert events == []
        assert not (work / 'DEPLOY_STARTED').exists()

    def test_optimized_python_aborts_before_production_actions(self):
        script = Path(__file__).with_name('overseas-context-deploy.py')
        for flags, optimize in ((['-O'], '0'), ([], '1')):
            result = subprocess.run([sys.executable, *flags, str(script),
                'overseas-20261015-abcdef0', 'build'], capture_output=True, text=True,
                env={**os.environ, 'PYTHONOPTIMIZE': optimize}, timeout=30)
            assert result.returncode != 0
            assert 'Python -O disables release safety assertions' in result.stderr


t.t.HotfixTests = ContextReleaseTests


@pytest.fixture
def baseline(monkeypatch, tmp_path):
    (tmp_path / 'frontend').mkdir()
    (tmp_path / 'frontend/package.json').write_text(json.dumps({'version': d.BASE_VERSION}))
    (tmp_path / 'OVERSEAS_RELEASE.json').write_text(json.dumps({'release': c.BASE_RELEASE}))
    monkeypatch.setattr(d.m, 'APP', tmp_path)
    monkeypatch.setattr(c, 'SYSTEMD', tmp_path / 'systemd')
    monkeypatch.setattr(d.m, 'EDGE', tmp_path / 'edge.conf')
    (tmp_path / 'infra').mkdir()
    body = 'location ^~ /api/overseas/v1/ { proxy_pass http://upstream;\n' + ''.join(
        f'{key} {value};\n' for key, value in d.proxy.DIRECTIVES.items()) + '}'
    d.m.EDGE.write_text(body)
    d.proxy.inner(d.m).write_text(body)
    for unit in d.u.UNITS:
        folder = c.SYSTEMD / (unit + '.service.d')
        folder.mkdir(parents=True)
        for name in ('90-overseas-update.conf', '95-codex-astra.conf'):
            (folder / name).write_text('historical baseline')
        (folder / d.u.DROP).write_text(c.a.native_pointer(c.BASE_NATIVE, unit))

    def run(*args, **kwargs):
        if args[1] == 'is-active':
            return 'active'
        if args[4] == 'WorkingDirectory':
            return str(c.BASE_NATIVE)
        if args[4] == 'MainPID':
            return '123'
        assert args[4] == 'DropInPaths'
        return ' '.join(str(p) for p in sorted((c.SYSTEMD / (args[2] + '.service.d')).glob('*.conf')))

    monkeypatch.setattr(d.m, 'run', run)
    monkeypatch.setattr(c.os, 'readlink', lambda path: str(c.BASE_NATIVE))
    monkeypatch.setattr(d.m, 'live', Mock(return_value={
        'State': {'Running': True, 'Health': {'Status': 'healthy'}},
        'HostConfig': {'Memory': d.resources.API_MEMORY}}))
    return tmp_path


@pytest.mark.parametrize('fault', ['version', 'release', 'memory', 'health', 'pointer', 'priority',
    'vendor-priority', 'unloaded', 'native-release', 'process-cwd', 'process-zero', 'inactive', 'edge', 'inner', 'duplicate'])
def test_preflight_rejects_baseline_drift(baseline, monkeypatch, fault):
    c.preflight()
    folder = c.SYSTEMD / (d.u.UNITS[0] + '.service.d')
    original = d.m.run
    if fault == 'version':
        (baseline / 'frontend/package.json').write_text('{"version":"0.2.34"}')
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
    elif fault in ('vendor-priority', 'unloaded', 'native-release', 'process-zero', 'inactive'):
        def run(*args, **kw):
            if args[1] == 'is-active':
                if fault == 'inactive':
                    raise RuntimeError('inactive')
                return original(*args, **kw)
            if fault == 'vendor-priority' and args[4] == 'DropInPaths':
                return original(*args, **kw) + ' /run/systemd/system/example.d/zz-override.conf'
            if fault == 'unloaded' and args[4] == 'DropInPaths': return ''
            if fault == 'native-release' and args[4] == 'WorkingDirectory': return '/old/backend'
            if fault == 'process-zero' and args[4] == 'MainPID': return '0'
            return original(*args, **kw)
        monkeypatch.setattr(d.m, 'run', run)
    elif fault == 'process-cwd':
        monkeypatch.setattr(c.os, 'readlink', lambda path: '/old/backend')
    elif fault in ('edge', 'inner'):
        path = d.m.EDGE if fault == 'edge' else d.proxy.inner(d.m)
        path.write_text(path.read_text().replace('500065536', '10485760'))
    else:
        d.m.EDGE.write_text(d.m.EDGE.read_text().replace('client_max_body_size', 'client_max_body_size 500065536; client_max_body_size'))
    with pytest.raises((AssertionError, RuntimeError)):
        c.preflight()


def test_proxy_preparation_preserves_both_layers(baseline, monkeypatch):
    monkeypatch.setattr(d.m, 'private', lambda path, body: path.write_text(body))
    work = baseline / 'work'; work.mkdir()
    include = baseline / 'infra/nginx.overseas-upload.inc'
    include.write_text(''.join(f'{key} {value};\n' for key, value in d.proxy.DIRECTIVES.items()))
    d.proxy.prepare(work, baseline, d.m)
    for label, path in (('edge', d.m.EDGE), ('inner', d.proxy.inner(d.m))):
        assert (work / f'upload-{label}-before.conf').read_bytes() == path.read_bytes()
        assert (work / f'upload-{label}-after.conf').read_bytes() == path.read_bytes()
    include.write_text('client_max_body_size 10m;')
    with pytest.raises(AssertionError, match='directive drift'):
        d.proxy.prepare(work, baseline, d.m)


@pytest.mark.parametrize('revision,column', [('overseas_0015', '0'), ('overseas_0016', '1'), ('overseas_0017', '0')])
def test_schema_drift_fails_without_migration(monkeypatch, revision, column):
    monkeypatch.setattr(d.r, 'sql', Mock(return_value='0028'))
    sql = Mock(side_effect=[revision, column])
    monkeypatch.setattr(d.u, 'sql', sql)
    with pytest.raises(AssertionError): d.schemas()
    assert all(call.args[0].startswith('SELECT ') for call in sql.call_args_list)


def test_schema_checks_keep_both_revisions_and_dropped_column(monkeypatch):
    monkeypatch.setattr(d.r, 'sql', Mock(return_value='0028'))
    monkeypatch.setattr(d.u, 'sql', Mock(side_effect=['overseas_0016', '0']))
    d.schemas()
    monkeypatch.setattr(d.r, 'sql', Mock(return_value='0027'))
    with pytest.raises(AssertionError): d.installed_schemas()


@pytest.mark.parametrize('value', [None, [], {}, {'conversationIds': []}, {'conversationIds': ['bad']},
    {'conversationIds': [123]}, {'conversationIds': TARGETS['conversationIds'] * 2},
    {**TARGETS, 'all': True}, {'conversationIds': [TARGETS['conversationIds'][0].upper()]}])
def test_invalid_targets_fail_before_prepare_writes(tmp_path, monkeypatch, value):
    if value is not None: (tmp_path / 'context-targets.json').write_text(json.dumps(value))
    prepare = Mock(); private = Mock()
    monkeypatch.setattr(c, '_prepare', prepare)
    monkeypatch.setattr(d.m, 'private', private)
    with pytest.raises((AssertionError, ValueError)):
        c.prepare(tmp_path, tmp_path, {}, 'image')
    prepare.assert_not_called(); private.assert_not_called()


def test_prepare_freezes_targets_before_original_preparation(tmp_path, monkeypatch):
    targets(tmp_path)
    monkeypatch.setattr(d.m, 'private', lambda path, body: path.write_text(body))
    def original(*args):
        c.frozen_targets(tmp_path)
        (tmp_path / 'PREPARED').write_text('image')
    prepare = Mock(side_effect=original)
    monkeypatch.setattr(c, '_prepare', prepare)
    c.prepare(tmp_path, tmp_path, {}, 'image')
    prepare.assert_called_once()
    with pytest.raises(AssertionError, match='already prepared'):
        c.prepare(tmp_path, tmp_path, {}, 'image')


@pytest.mark.parametrize('fault', [None, 'backup', 'drain', 'targets', 'stale', 'helper', 'unverified', 'empty', 'changed'])
def test_recovery_requires_backup_drain_frozen_targets_and_verified_result(tmp_path, monkeypatch, fault):
    work = tmp_path / 'work'; work.mkdir()
    backup = tmp_path / 'backup'; backup.mkdir()
    targets(work)
    if fault != 'backup': (backup / 'COMPLETE').write_text('verified')
    if fault != 'drain': (work / 'EXECUTORS_STOPPED').write_text('verified')
    (work / 'native-target').write_text('/new/backend')
    marker = work / 'CONTEXT_RECOVERY_VERIFIED'
    if fault == 'stale': marker.write_text('old')
    if fault == 'targets': (work / 'context-targets.json').write_text(json.dumps(TARGETS, indent=2))
    monkeypatch.setattr(d, 'schemas', Mock())
    def recover(*args):
        if fault == 'helper': raise RuntimeError('recovery failure')
        if fault == 'unverified': return
        marker.write_text('' if fault == 'empty' else 'verified')
        if fault == 'changed': (work / 'context-targets.json').write_text(json.dumps(TARGETS, indent=2))
    helper = Mock(side_effect=recover)
    monkeypatch.setattr(c, 'recovery_module', Mock(return_value=SimpleNamespace(recover_contexts=helper)))
    if fault:
        with pytest.raises((AssertionError, RuntimeError)):
            c.before_switch(work, tmp_path, 'image', {'overseas': {}}, backup)
        if fault in ('backup', 'drain', 'targets', 'stale'): helper.assert_not_called()
    else:
        c.before_switch(work, tmp_path, 'image', {'overseas': {}}, backup)
        helper.assert_called_once_with(work, tmp_path, Path('/new/backend'), {'overseas': {}}, backup)
        assert d.schemas.call_count == 2


def test_manifest_requires_context_runtime_recovery_and_real_probe(tmp_path, monkeypatch):
    source = tmp_path / 'src'; (source / 'frontend').mkdir(parents=True)
    manifest = {'release': 'fixture', 'frontendVersion': d.TARGET_VERSION,
        'migration': '0028', 'overseasMigration': 'overseas_0016', 'files': dict.fromkeys(c.REQUIRED, 'digest')}
    (source / 'frontend/package.json').write_text(json.dumps({'version': d.TARGET_VERSION}))
    monkeypatch.setattr(d.r, 'hashes', Mock())
    (source / 'release.json').write_text(json.dumps(manifest))
    assert c.validate(tmp_path, 'fixture')[1] == manifest
    for name in c.REQUIRED:
        incomplete = {**manifest, 'files': {n: h for n, h in manifest['files'].items() if n != name}}
        (source / 'release.json').write_text(json.dumps(incomplete))
        with pytest.raises(AssertionError, match='missing from manifest'): c.validate(tmp_path, 'fixture')


def test_legacy_entries_keep_versions_schemas_and_hooks():
    upload = load('overseas-upload-deploy')
    attachment = load('overseas-attachments-deploy')
    assert (upload.TARGET_VERSION, upload.BASE_VERSION, upload.TARGET_MIGRATION, upload.u.DROP) == (
        '0.2.33', '0.2.32', 'overseas_0015', '90-overseas-update.conf')
    assert (attachment.d.TARGET_VERSION, attachment.d.BASE_VERSION) == ('0.2.35', '0.2.34')
    assert attachment.d.before_switch == attachment.migrate
    assert (d.TARGET_VERSION, d.BASE_VERSION, d.TARGET_MIGRATION, d.u.DROP) == (
        '0.2.36', '0.2.35', 'overseas_0016', '99-overseas-upload.conf')
    assert d.before_switch == c.before_switch and d.schemas == c.a.installed_schemas


def test_cli_release_date_and_retention_are_pinned(monkeypatch):
    monkeypatch.setattr(d.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(d.os, 'umask', Mock())
    validate = Mock(return_value=(Path('/source'), {}, 'image')); prepare = Mock()
    monkeypatch.setattr(d, 'validate', validate); monkeypatch.setattr(d, 'prepare', prepare)
    monkeypatch.setattr(sys, 'argv', ['context', 'overseas-20261015-abcdef0', 'prepare'])
    c.main(); prepare.assert_called_once()
    validate.reset_mock()
    monkeypatch.setattr(sys, 'argv', ['context', 'overseas-20261014-abcdef0', 'prepare'])
    with pytest.raises(AssertionError): c.main()
    validate.assert_not_called()
    assert "d.m.module('release-retention').managed(main)" in Path(c.__file__).read_text()
