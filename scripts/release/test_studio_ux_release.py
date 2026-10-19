"""Studio UX release safety, package contract and inherited cutover fault matrix."""
import copy
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from unittest.mock import Mock

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


a = load('overseas-studio-ux-deploy')
d = a.d
p = load('package-studio-ux')
t = load('test_overseas_upload')
t.d = t.t.d = d
t.p = d.proxy


class StudioUXReleaseTests(t.UploadReleaseTests):
    def setup_deploy(self, failure=None):
        work, data, events = super().setup_deploy(failure)
        self.mock(d, 'preflight')
        self.mock(d, 'before_switch')
        return work, data, events

    def test_closed_waits_for_reload_and_times_out_if_still_open(self):
        probe = self.mock(d.m, 'run', side_effect=['401'] * 4 + ['503'] * 4)
        self.mock(a.c.time, 'sleep')
        d.closed()
        assert probe.call_count == 8
        with pytest.raises(AssertionError, match='did not reach'):
            d.closed(timeout=0)

    def test_resource_checks_detect_domestic_restart_and_overseas_mount_change(self):
        # Preserve the inherited ID/mount/config fault matrix separately from added runtime checks.
        self.mock(d.resources, 'unchanged', new=a._unchanged)
        super().test_resource_checks_detect_domestic_restart_and_overseas_mount_change()

    def test_optimized_python_aborts_before_production_actions(self):
        for flags, optimize in ((['-O'], '0'), ([], '1')):
            result = subprocess.run([sys.executable, *flags,
                str(Path(__file__).with_name('overseas-studio-ux-deploy.py')),
                'overseas-20261019-abcdef0', 'build'], capture_output=True, text=True,
                env={**os.environ, 'PYTHONOPTIMIZE': optimize}, timeout=30)
            assert result.returncode != 0
            assert 'Python -O disables release safety assertions' in result.stderr

    def test_migration_failure_never_switches_or_reopens(self):
        work, _, events = self.setup_deploy()
        d.before_switch.side_effect = RuntimeError('migration failure')
        with pytest.raises(RuntimeError, match='migration failure'):
            self.deploy(work)
        assert json.loads((work / 'FAILURE.json').read_text())['phase'] == 'migration'
        assert not any(row[0] in ('switch', 'open', 'installed') for row in events)
        assert [row[0] for row in events].count('close') == 2


t.t.HotfixTests = StudioUXReleaseTests


def test_only_api_restart_policy_may_be_persisted():
    before = {'services': {'api': {'image': 'old', 'environment': {'SAFE': 'yes'}},
                           'redis': {'restart': 'no'}}}
    after = copy.deepcopy(before)
    after['services']['api'].update(a.overlay('/source', 'tested')['services']['api'])
    a.same_settings(before, after, d.m)
    for service, key, value in [('api', 'restart', 'always'), ('redis', 'restart', 'unless-stopped'),
                               ('api', 'environment', {'SAFE': 'no'})]:
        bad = copy.deepcopy(after)
        bad['services'][service][key] = value
        with pytest.raises(AssertionError):
            a.same_settings(before, bad, d.m)


def test_all_three_domestic_native_services_are_guarded(monkeypatch):
    probe = Mock(return_value={'pid': 1})
    monkeypatch.setattr(a.c, 'native_state', probe)
    assert set(a.domestic_native()) == set(a.DOMESTIC_UNITS)
    assert set(d.m.UNITS) == {*a.DOMESTIC_UNITS, *d.u.UNITS}
    assert all(call.args[1] == a.c.DOMESTIC_NATIVE for call in probe.call_args_list)


@pytest.mark.parametrize('fault', [None, 'image', 'restart'])
def test_preflight_requires_real_installed_api_baseline(monkeypatch, fault):
    monkeypatch.setattr(a, '_preflight', Mock())
    monkeypatch.setattr(d.m, 'live', lambda _: {'Image': 'changed' if fault == 'image' else a.BASE_IMAGE,
        'HostConfig': {'RestartPolicy': {'Name': 'no' if fault == 'restart' else a.RESTART}}})
    if fault:
        with pytest.raises(AssertionError): a.preflight()
    else:
        a.preflight()


@pytest.mark.parametrize('fault', [None, 'domestic', 'revision', 'usage', 'visibility', 'audit'])
def test_schema_gate_requires_0030_and_exact_audit_transition(monkeypatch, fault):
    monkeypatch.setattr(d.r, 'sql', lambda _: '0029' if fault == 'domestic' else '0030')
    values = ['wrong' if fault == 'revision' else 'overseas_0017',
              '1' if fault == 'usage' else '0', '0' if fault == 'visibility' else '1',
              '1' if fault == 'audit' else '0']
    monkeypatch.setattr(d.u, 'sql', Mock(side_effect=values))
    if fault:
        with pytest.raises(AssertionError): a.schemas()
    else:
        a.schemas()


def test_unchanged_checks_other_overseas_runtime_and_api_restart(monkeypatch):
    monkeypatch.setattr(a, '_unchanged', Mock())
    runtime = {'api': {'image': 'old', 'restart': {'Name': 'unless-stopped'}},
               'redis': {'image': 'redis-image', 'restart': {'Name': 'always'}}}
    data = {'overseas': {'runtime': runtime}}
    after = copy.deepcopy(data)
    after['overseas']['runtime']['api']['image'] = 'new'
    monkeypatch.setattr(d.m, 'topology', lambda: after)
    monkeypatch.setattr(d.u, 'API', 'api')
    a.unchanged(data, None, None, d.m, d.u, None)
    after['overseas']['runtime']['api']['restart']['Name'] = 'no'
    with pytest.raises(AssertionError): a.unchanged(data, None, None, d.m, d.u, None)
    after['overseas']['runtime']['api']['restart']['Name'] = 'unless-stopped'
    after['overseas']['runtime']['redis']['image'] = 'wrong'
    with pytest.raises(AssertionError): a.unchanged(data, None, None, d.m, d.u, None)


@pytest.mark.parametrize('fault', [None, 'restore', 'drift'])
def test_backup_completion_requires_isolated_restore_and_exact_rows(tmp_path, monkeypatch, fault):
    work = tmp_path / 'overseas-20261019-abcdef0'
    work.mkdir()
    (work / 'EXECUTORS_STOPPED').touch()
    (work / 'topology.json').write_text('{}')
    monkeypatch.setattr(d.u, 'pending', lambda: 0)
    monkeypatch.setattr(d.u, 'sql', lambda _: '0')
    for name in ('backup_config', 'dump', 'secure_tree'):
        monkeypatch.setattr(a.b, name, Mock())
    restore = Mock(side_effect=RuntimeError('restore') if fault == 'restore' else None)
    monkeypatch.setattr(a.b, 'restore_check', restore)
    monkeypatch.setattr(a, 'fingerprint', Mock(side_effect=[{'table': 'original'},
        {'table': 'changed' if fault == 'drift' else 'original'}]))
    monkeypatch.setattr(d.m, 'private', lambda path, value: path.write_text(
        value if isinstance(value, str) else json.dumps(value)))
    destination = tmp_path / 'backup'
    if fault:
        with pytest.raises((RuntimeError, AssertionError)):
            a.backup(work, destination, {})
        assert not (destination / 'COMPLETE').exists()
    else:
        a.backup(work, destination, {})
        assert (destination / 'COMPLETE').is_file()
        restore.assert_called_once()


@pytest.mark.parametrize('fault', [None, 'backup', 'drain', 'schema', 'config', 'migration', 'rows'])
def test_migration_safety_and_existing_rows(tmp_path, monkeypatch, fault):
    work, backup = tmp_path / 'work', tmp_path / 'backup'
    work.mkdir(); backup.mkdir()
    if fault != 'backup': (backup / 'COMPLETE').touch()
    if fault != 'drain': (work / 'EXECUTORS_STOPPED').touch()
    (backup / 'fingerprints.json').write_text('{"archives":"original"}')
    before = {'services': {'migrate': {'image': 'old', 'environment': {'ROLE': 'owner'}}, 'api': {'image': 'old'}}}
    (work / 'overseas-compose.private.json').write_text(json.dumps(before))
    after = copy.deepcopy(before)
    after['services']['migrate']['image'] = 'tested'
    if fault == 'config': after['services']['api']['image'] = 'wrong'
    monkeypatch.setattr(a, 'schemas', Mock(side_effect=AssertionError('schema') if fault == 'schema' else None))
    monkeypatch.setattr(a, 'installed_schemas', Mock())
    monkeypatch.setattr(a, 'fingerprint', Mock(side_effect=[{'archives': 'original'},
        {'archives': 'changed' if fault == 'rows' else 'original', a.AUDIT_TABLE: '3:backfilled'}]))
    compose = Mock(side_effect=[json.dumps(before), json.dumps(after), RuntimeError('migration') if fault == 'migration' else ''])
    monkeypatch.setattr(d.m, 'compose', compose)
    monkeypatch.setattr(d.m, 'private', lambda path, value: path.write_text(
        value if isinstance(value, str) else json.dumps(value)))
    if fault:
        with pytest.raises((AssertionError, RuntimeError)):
            a.migrate(work, tmp_path, 'tested', {'overseas': {}}, backup)
        assert not (work / 'MIGRATION_VERIFIED').exists()
        if fault in ('backup', 'drain', 'schema', 'config'):
            assert not (work / 'MIGRATION_STARTED').exists()
    else:
        a.migrate(work, tmp_path, 'tested', {'overseas': {}}, backup)
        assert (work / 'MIGRATION_VERIFIED').is_file()
        assert compose.call_args.args[-1] == 'overseas_0018'


def test_package_contract_privacy_and_complete_helper_selection():
    values = dict.fromkeys(p.REQUIRED, b'')
    values.update({'frontend/package.json': b'{"version":"0.2.41"}',
        'frontend/dist/index.html': b'<script src="/assets/main.js"></script>',
        'frontend/dist/assets/main.js': b'console.log(1)'})
    p.validate(values)
    for name in p.REQUIRED:
        assert p.selected(name if name.startswith('scripts/') else p.p.APP + name) == name or name.startswith('frontend/dist/')
        with pytest.raises(ValueError, match='Missing'):
            p.validate({key: value for key, value in values.items() if key != name})
    assert (p.p.DOMESTIC_MIGRATION, p.p.OVERSEAS_MIGRATION, p.p.RELEASE_PREFIX) == ('0030', 'overseas_0018', 'overseas-20261019-')
    repo = Path(__file__).resolve().parents[2]
    paths = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=repo, text=True).split('\0')
    for path in paths:
        if name := p.selected(path):
            p.p.m.common.privacy_check(name, p.p.m.common.normalized((repo / path).read_bytes()))


def test_deploy_transitive_helpers_are_packaged():
    folder = Path(__file__).parent
    seen, todo = set(), ['overseas-studio-ux-deploy.py', 'release-retention.py']
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        assert p.selected('scripts/release/' + name) == 'scripts/release/' + name
        tree = ast.parse((folder / name).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and node.args:
                method = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ''
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    candidate = (arg.value if method == 'with_name' else
                                 arg.value + '.py' if method == 'module' else '')
                    if candidate and (folder / candidate).is_file():
                        todo.append(candidate)
    assert {'member-release-backup.py', 'overseas-update-runtime.py',
            'release-retention-state.py', 'release-build.py'} <= seen


def test_archive_manifest_has_current_schema_and_exact_hashes(tmp_path, monkeypatch):
    files = dict.fromkeys(p.REQUIRED, b'')
    files.update({'frontend/package.json': b'{"version":"0.2.41"}',
        'frontend/dist/index.html': b'<script src="/assets/main.js"></script>',
        'frontend/dist/assets/main.js': b'console.log(1)'})
    sources = {}
    for name, body in files.items():
        tracked = name if name.startswith('scripts/') else p.p.APP + name
        local = tmp_path / tracked
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(body)
        if not name.startswith('frontend/dist/'):
            sources[tracked] = body
    sources.update({'scripts/release/' + name: b'helper' for name in p.p.PACKAGING_HELPERS})
    commit = 'abcdef0123456789abcdef0123456789abcdef0123'
    def git(_repo, *args):
        if args[0] == 'status': return b''
        if args[0] == 'rev-parse': return commit.encode()
        if args[0] == 'ls-files': return ('\0'.join(sources) + '\0').encode()
        if args[0] == 'show': return sources[args[1].split(':', 1)[1]]
        pytest.fail(repr(args))
    monkeypatch.setattr(p.p.m.common, 'git', git)
    monkeypatch.setattr(p.p.m.common, 'reviewed_status', lambda *_: {'currentId': 'approved'})
    audit = p.build(tmp_path)
    path = tmp_path / 'output/release/overseas-20261019-abcdef0/release.tar.gz'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == audit['sha256']
    with tarfile.open(path, 'r:gz') as archive:
        manifest = json.load(archive.extractfile('release.json'))
        assert (manifest['migration'], manifest['overseasMigration'], manifest['frontendVersion']) == ('0030', 'overseas_0018', '0.2.41')
        assert manifest['candidateId'] == 'approved'
        for name, digest in manifest['files'].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest
