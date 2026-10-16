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


a = load('overseas-materials-deploy')
d = a.d
t = load('test_overseas_upload')
t.d = t.t.d = d
t.p = d.proxy


class MaterialsReleaseTests(t.UploadReleaseTests):
    def test_closed_waits_for_reload_and_times_out_if_still_open(self):
        probe = self.mock(d.m, 'run', side_effect=['401'] * 4 + ['503'] * 4)
        self.mock(a.c.time, 'sleep')
        d.closed()
        assert probe.call_count == 8
        with pytest.raises(AssertionError, match='did not reach'):
            d.closed(timeout=0)

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
        assert json.loads((work / 'verification.json').read_text())['overseasMigration'] == 'overseas_0017'
        assert 'Never downgrade or restore databases' in (work / 'RECOVERY.txt').read_text()

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
        script = Path(__file__).with_name('overseas-materials-deploy.py')
        for flags, optimize in ((['-O'], '0'), ([], '1')):
            result = subprocess.run([sys.executable, *flags, str(script),
                'overseas-20261016-abcdef0', 'build'], capture_output=True, text=True,
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


t.t.HotfixTests = MaterialsReleaseTests


@pytest.mark.parametrize('fault', [None, 'backup', 'drain', 'baseline', 'config', 'migration', 'revision', 'remaining-column'])
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
    monkeypatch.setattr(a, 'schemas', Mock(side_effect=AssertionError('baseline') if fault == 'baseline' else None))
    monkeypatch.setattr(d.r, 'sql', Mock(return_value='0029'))
    sql = Mock(side_effect=['overseas_0016' if fault == 'revision' else 'overseas_0017',
                           '1' if fault == 'remaining-column' else '0', '1'])
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
        if fault in ('backup', 'drain', 'baseline', 'config'):
            assert not (work / 'MIGRATION_STARTED').exists()
            assert not any('run' in call.args for call in compose.call_args_list)
    else:
        a.migrate(work, tmp_path, 'sha256:tested', {'overseas': {'group': 'overseas'}}, backup)
        assert (work / 'MIGRATION_VERIFIED').read_text() == 'overseas_0017: list visibility only'
        assert compose.call_args.args[1:] == ('run', '--rm', '--no-deps', '--pull', 'never',
            'migrate', 'alembic', '-c', 'alembic.overseas.ini', 'upgrade', 'overseas_0017')
        overlay = json.loads((work / 'overseas-migration-overlay.json').read_text())
        assert set(overlay['services']) == {'migrate'}
        assert overlay['services']['migrate']['image'] == 'sha256:tested'
