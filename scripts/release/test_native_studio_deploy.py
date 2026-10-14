"""Offline safety tests for forward-only overseas native studio deployment."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location('studio_deploy_test', Path(__file__).with_name('native-studio-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
s, h, m = d.s, d.h, d.m


def save(path, value):
    Path(path).write_text(value if isinstance(value, str) else json.dumps(value))


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    work = tmp_path / 'work'
    work.mkdir()
    for name in ('PREPARED', 'INSTALL_TEST_IMAGE_ID'):
        save(work / name, 'sha256:tested')
    data = {group: {'group': group} for group in m.GROUPS}
    save(work / 'topology.json', data)
    native = {'pid': 123, 'cwd': '/old/domestic'}
    save(work / 'domestic-native.json', native)
    save(work / 'native-target', '/new/overseas/backend')
    edge = tmp_path / 'edge.conf'
    save(edge, 'location ^~ /api/overseas/v1/ { proxy_pass http://overseas; }')
    (tmp_path / 'frontend').mkdir()
    save(tmp_path / 'frontend/package.json', {'version': s.VERSION})
    events, failure = [], {'at': None}

    def event(name, *args):
        events.append((name, *args))
        if name == failure['at']:
            raise RuntimeError(name)

    def backup(work, destination, data):
        event('backup')
        destination.mkdir(parents=True)
        save(destination / 'COMPLETE', 'verified')

    monkeypatch.setattr(d, 'BACKUPS', tmp_path / 'backups')
    monkeypatch.setattr(m, 'APP', tmp_path)
    monkeypatch.setattr(m, 'EDGE', edge)
    monkeypatch.setattr(m, 'private', save)
    monkeypatch.setattr(m, 'image_id', Mock(return_value='sha256:tested'))
    monkeypatch.setattr(m, 'topology', Mock(return_value=data))
    monkeypatch.setattr(h, 'domestic_native', lambda: native)
    monkeypatch.setattr(s, 'schemas', Mock(side_effect=lambda value: event('schema', value)))
    monkeypatch.setattr(s, 'previous_version', Mock())
    monkeypatch.setattr(s, 'prepared_settings', lambda *a: event('settings'))
    monkeypatch.setattr(m, 'assets_safe', lambda *a: event('assets'))
    monkeypatch.setattr(d.r, 'hashes', Mock())
    monkeypatch.setattr(d.r, 'sql', lambda query: '0028')
    monkeypatch.setattr(d.u, 'sql', lambda query: s.OLD_SCHEMA)
    monkeypatch.setattr(h, 'close_edge', lambda *a: event('close'))
    monkeypatch.setattr(h, 'closed', lambda: event('closed'))
    monkeypatch.setattr(h, 'drain_and_stop', lambda *a: event('drain'))

    def compose(data, *args, **kwargs):
        event('compose', data['group'], *args)
        if args[0] == 'run':
            assert (work / 'MIGRATION_STARTED').exists()
            assert (tmp_path / 'backups/fixture/COMPLETE').exists()
            event('migration')

    monkeypatch.setattr(m, 'compose', compose)
    monkeypatch.setattr(m, 'run', lambda *a, **kw: event('run', *a))
    monkeypatch.setattr(d.u, 'backup', backup)
    monkeypatch.setattr(d.u, 'switch_native', lambda *a: event('switch'))
    monkeypatch.setattr(d.u, 'reload_edge', lambda: event('open'))
    monkeypatch.setattr(s, 'installed', lambda *a: event('installed'))
    monkeypatch.setattr(h, 'resources_unchanged', lambda *a: event('resources'))
    monkeypatch.setattr(d.r, 'publish', lambda *a: event('publish'))
    monkeypatch.setattr(d.verify, 'status', lambda *a: '401')
    for name in ('proxy', 'frontend', 'public'):
        monkeypatch.setattr(d.verify, name, lambda *a, name=name: event(name))
    return work, tmp_path, events, failure


def deploy(fixture):
    work, source, _, _ = fixture
    d.deploy(work, source, {'release': 'fixture', 'files': {}}, 'image')


def test_migration_order_pinned_image_and_overseas_only(deployment):
    work, root, events, _ = deployment
    deploy(deployment)
    names = [e[0] for e in events]
    order = ['close', 'closed', 'drain', 'backup', 'migration', 'switch', 'installed',
             'proxy', 'publish', 'frontend', 'open', 'public', 'resources']
    assert [names.index(n) for n in order] == sorted(names.index(n) for n in order)
    commands = [e for e in events if e[0] == 'compose']
    assert all(e[1] == 'overseas' for e in commands)
    migration = next(e for e in commands if 'migrate' in e)
    assert migration == ('compose', 'overseas', 'run', '--rm', '--no-deps', '--pull', 'never',
                         'migrate', 'alembic', '-c', 'alembic.overseas.ini', 'upgrade', s.NEW_SCHEMA)
    assert all('--no-deps' in e and '--no-build' in e for e in commands if 'up' in e)
    assert [e for e in events if e[:2] == ('run', 'systemctl')] == [('run', 'systemctl', 'start', *d.u.UNITS)]
    assert not any('restore' in str(e) or 'skills_install' in str(e) for e in events)
    assert (work / 'PHASE').read_text() == 'complete'
    assert (work / 'MIGRATION_VERIFIED').read_text() == s.NEW_SCHEMA
    assert not (root / 'MEMBER_RELEASE.json').exists()
    record = json.loads((work / 'verification.json').read_text())
    assert (record['migration'], record['overseasMigration'], record['frontendVersion']) == ('0028', s.NEW_SCHEMA, s.VERSION)


@pytest.mark.parametrize('failure', ['close', 'closed', 'drain', 'backup', 'migration', 'switch',
                                   'installed', 'proxy', 'publish', 'frontend', 'open', 'public', 'resources'])
def test_failure_keeps_intake_closed_and_records_actual_schema(deployment, failure):
    work, _, events, fail = deployment
    fail['at'] = failure
    with pytest.raises(RuntimeError, match=failure):
        deploy(deployment)
    report = json.loads((work / 'FAILURE.json').read_text())
    assert report['apiStopped'] is True
    assert report['edgeClosed'] is (failure not in ('close', 'closed'))
    assert report['overseasSchema'] == s.OLD_SCHEMA
    assert ('close',) in events[-3:]
    assert events[-1] == ('compose', 'overseas', 'stop', '-t', '30', 'api')
    assert not any(e[:3] == ('run', 'systemctl', 'stop') for e in events)
    assert not (work / 'verification.json').exists()
    if failure == 'migration':
        assert report['phase'] == 'migration' and report['migrationStarted']
        assert (work / 'MIGRATION_STARTED').exists()
        assert not (work / 'MIGRATION_VERIFIED').exists()
        assert ('switch',) not in events


@pytest.mark.parametrize('marker', ['DEPLOY_STARTED', 'MIGRATION_STARTED'])
def test_attempt_is_not_replayed(deployment, marker):
    work, _, events, _ = deployment
    save(work / marker, 'previous attempt')
    with pytest.raises(AssertionError, match='recovery'):
        deploy(deployment)
    assert events == []


def test_image_drift_blocks_cutover_before_closure(deployment):
    work, _, events, _ = deployment
    m.image_id.return_value = 'sha256:drift'
    with pytest.raises(AssertionError, match='image drift'):
        deploy(deployment)
    assert events == [] and not (work / 'DEPLOY_STARTED').exists()


def test_image_rechecked_at_migration_boundary(deployment):
    work, _, events, _ = deployment
    m.image_id.side_effect = ['sha256:tested', 'sha256:drift']
    with pytest.raises(AssertionError, match='Approved image drift'):
        deploy(deployment)
    assert not (work / 'MIGRATION_STARTED').exists()
    assert ('migration',) not in events and ('switch',) not in events
    assert json.loads((work / 'FAILURE.json').read_text())['apiStopped']


def test_topology_drift_blocks_cutover(deployment):
    work, _, events, _ = deployment
    m.topology.return_value = {'drift': True}
    with pytest.raises(AssertionError, match='Topology drift'):
        deploy(deployment)
    assert not (work / 'DEPLOY_STARTED').exists()
    assert ('close',) not in events


def test_wrong_old_schema_blocks_before_cutover(deployment):
    work, _, events, _ = deployment
    s.schemas.side_effect = AssertionError('Overseas schema drift')
    with pytest.raises(AssertionError, match='schema drift'):
        deploy(deployment)
    assert events == [] and not (work / 'DEPLOY_STARTED').exists()


def test_failed_schema_verification_never_switches(deployment):
    work, _, events, _ = deployment
    s.schemas.side_effect = [None, None, AssertionError('migration did not advance')]
    with pytest.raises(AssertionError, match='did not advance'):
        deploy(deployment)
    assert ('migration',) in events and ('switch',) not in events
    assert not (work / 'MIGRATION_VERIFIED').exists()


def test_unverified_backup_blocks_migration(deployment, monkeypatch):
    work, _, events, _ = deployment
    monkeypatch.setattr(d.u, 'backup', lambda work, destination, data: destination.mkdir(parents=True))
    with pytest.raises(AssertionError, match='No verified complete backup'):
        deploy(deployment)
    assert ('migration',) not in events and ('switch',) not in events
    assert not (work / 'MIGRATION_STARTED').exists()
    assert json.loads((work / 'FAILURE.json').read_text())['apiStopped']


@pytest.mark.parametrize('flags,optimize', [(['-O'], '0'), ([], '1')])
def test_optimized_python_aborts(flags, optimize):
    script = Path(__file__).with_name('native-studio-deploy.py')
    result = subprocess.run([sys.executable, *flags, str(script), 'overseas-20261014-abcdef0', 'build'],
        capture_output=True, text=True, env={**os.environ, 'PYTHONOPTIMIZE': optimize}, timeout=30)
    assert result.returncode != 0
    assert 'RuntimeError: Python -O disables release safety assertions' in result.stderr
