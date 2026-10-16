import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('retirement_deploy', Path(__file__).with_name('retirement-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


@pytest.fixture
def release(monkeypatch, tmp_path):
    events = []
    data = {'domestic': {'project': 'domestic'}}
    (tmp_path / 'PREPARED').write_text('sha256:candidate')
    (tmp_path / 'topology.json').write_text(json.dumps(data))
    (tmp_path / 'domestic-compose.private.json').write_text('{}')
    monkeypatch.setattr(d.m, 'image_id', lambda *_: 'sha256:candidate')
    monkeypatch.setattr(d.n, 'topology', lambda: data)
    monkeypatch.setattr(d.n, 'baseline', lambda: None)
    monkeypatch.setattr(d.m, 'same_settings', lambda *_: None)
    monkeypatch.setattr(d.m, 'assets_safe', lambda *_: None)
    monkeypatch.setattr(d.m, 'private', lambda path, value: events.append(('save', path.name)))
    monkeypatch.setattr(d.m, 'run', lambda *args, **kw: events.append(('run', *args)) or '')

    def compose(_data, *args, **kw):
        events.append(('compose', *args))
        return '{}' if args[0] == 'config' else ''

    def sql(statement):
        if statement.startswith('SELECT version_num'):
            return '0030'
        if statement.startswith('SELECT paused'):
            return 'f'
        events.append(('sql', statement))
        return ''

    monkeypatch.setattr(d.m, 'compose', compose)
    monkeypatch.setattr(d.r, 'sql', sql)
    monkeypatch.setattr(d.r, 'publish', lambda *_: events.append(('publish',)))
    for owner, name, label in ((d.gate, 'close', 'close'), (d.gate, 'verify_closed', 'closed-verified'),
                               (d.gate, 'open_intake', 'open'), (d.drain, 'stop', 'drained'),
                               (d.backup, 'create', 'restore-tested'), (d.backup, 'verify_after', 'rows-preserved'),
                               (d.n.n, 'switch', 'switch'), (d.n, 'unchanged_other_groups', 'others-unchanged'),
                               (d, 'verify', 'installed-verified'), (d, 'public_verify', 'public-verified')):
        monkeypatch.setattr(owner, name, lambda *_, label=label: events.append((label,)))
    return tmp_path, tmp_path / 'source', {'release': 'domestic-retire-20261016-abcdef0'}, 'image', events


def test_cutover_orders_restore_migration_fingerprints_and_new_cleanup(release):
    *args, events = release
    d.deploy(*args)
    names = [row[0] for row in events]
    assert names.index('close') < names.index('drained') < names.index('restore-tested')
    assert names.index('restore-tested') < names.index('rows-preserved') < names.index('switch')
    assert names.index('switch') < names.index('installed-verified') < names.index('publish') < names.index('open')
    assert ('run', 'systemctl', 'start', *d.n.n.UNITS) in events
    assert not any('overseas' in row or 'identity-api' in row or 'web' in row for row in events)


@pytest.mark.parametrize('failure', ['drain', 'backup', 'fingerprint', 'switch', 'verify', 'public'])
def test_failures_never_restore_database_or_start_old_processes(release, monkeypatch, failure):
    *args, events = release
    owner, name = {'drain': (d.drain, 'stop'), 'backup': (d.backup, 'create'),
                   'fingerprint': (d.backup, 'verify_after'), 'switch': (d.n.n, 'switch'),
                   'verify': (d, 'verify'), 'public': (d, 'public_verify')}[failure]

    def fail(*_):
        raise RuntimeError('fault injection')

    monkeypatch.setattr(owner, name, fail)
    with pytest.raises(RuntimeError, match='fault injection'):
        d.deploy(*args)
    assert events[-1] == ('close',)
    assert ('save', 'RECOVERY_REQUIRED.json') in events
    assert ('save', 'VERIFIED') not in events
    assert not any('pg_restore' in row or 'restart' in row for row in events)
    if failure in ('drain', 'backup', 'fingerprint', 'switch'):
        assert not any(row[:3] == ('run', 'systemctl', 'start') for row in events)


def test_process_drift_stops_before_closing_intake(release, monkeypatch):
    *args, events = release
    monkeypatch.setattr(d.n, 'topology', lambda: {'nativePidChanged': True})
    with pytest.raises(AssertionError, match='topology changed'):
        d.deploy(*args)
    assert events == []
