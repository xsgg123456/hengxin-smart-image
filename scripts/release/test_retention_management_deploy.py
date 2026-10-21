import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('retention_deploy', Path(__file__).with_name('retention-management-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
RELEASE = 'domestic-retention-20261021-abcdef0'


@pytest.fixture
def release(monkeypatch, tmp_path):
    events = []
    data = {'domestic': {'project': 'domestic'}}
    for name, value in {'PREPARED': 'candidate', 'topology.json': json.dumps(data),
        'domestic-compose.private.json': '{}', 'native-target': str(tmp_path / 'native/backend')}.items():
        (tmp_path / name).write_text(value)
    monkeypatch.setattr(d, 'BACKUPS', tmp_path / 'backup')
    monkeypatch.setattr(d.m, 'image_id', lambda *_: 'candidate')
    monkeypatch.setattr(d.s, 'topology', lambda: data)
    monkeypatch.setattr(d.s, 'baseline', lambda: None)
    monkeypatch.setattr(d.s, 'same_settings', lambda *_: None)
    monkeypatch.setattr(d.m, 'assets_safe', lambda *_: None)
    monkeypatch.setattr(d.r, 'hashes', lambda *_: None)
    def private(path, value):
        events.append(('save', path.name, value))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value))
    monkeypatch.setattr(d.m, 'private', private)
    monkeypatch.setattr(d.m, 'run', lambda *args, **kw: events.append(('run', *args)))
    def compose(_data, *args, **kw):
        events.append(('compose', *args))
        return '{}' if args[0] == 'config' else ''
    monkeypatch.setattr(d.m, 'compose', compose)
    def sql(query):
        if query.startswith('SELECT paused'): return 'f'
        events.append(('sql', query))
        return '0032'
    monkeypatch.setattr(d.r, 'sql', sql)
    def backup(work, destination, *_):
        events.append(('backup',))
        destination.mkdir(parents=True)
        (destination / 'COMPLETE').write_text('yes')
    monkeypatch.setattr(d.backup, 'create', backup)
    for owner, name in ((d.gate, 'close'), (d.gate, 'verify_closed'), (d.gate, 'open_intake'),
        (d.s.p, 'graceful_stop'), (d.drain, 'stop'), (d.backup, 'verify_after'),
        (d.checks, 'migrated'), (d.checks, 'frontend'), (d.checks, 'mark_start'), (d.checks, 'first_scan'),
        (d.n, 'switch'), (d.n, 'verify'), (d.s, 'installed'), (d.s, 'unchanged'),
        (d.r, 'publish'), (d.r, 'worker'), (d.s.p.base, 'public_verify')):
        monkeypatch.setattr(owner, name, lambda *args, label=name: events.append((label, *args)))
    monkeypatch.setattr(d.n, 'stop', lambda unit: events.append(('pause-cleanup', unit)))
    return tmp_path, tmp_path / 'source', {'release': RELEASE, 'files': {'backend/app.py': 'hash'}}, 'image', events


def test_cleanup_only_after_restore_migration_consumers_and_frontend(release):
    *args, events = release
    d.deploy(*args)
    labels = [e[0] for e in events]
    migrate = next(i for i, e in enumerate(events) if e[:2] == ('compose', 'run'))
    cleanup = next(i for i, e in enumerate(events) if e[:3] == ('run', 'systemctl', 'start') and d.n.RETENTION in e)
    assert labels.index('close') < labels.index('graceful_stop') < labels.index('stop') < labels.index('backup') < migrate
    assert migrate < labels.index('verify_after') < labels.index('switch') < labels.index('publish')
    assert labels.index('frontend') < cleanup < labels.index('first_scan') < labels.index('open_intake')
    switches = [e for e in events if e[:2] == ('compose', 'up')]
    assert switches[0][-3:] == ('api', 'api-image-worker', 'image-variants')
    assert switches[1][-2:] == ('outbox', 'api-image-outbox')
    assert events.index(switches[1]) > labels.index('first_scan')
    assert (args[0] / 'VERIFIED').exists()


@pytest.mark.parametrize('owner,name', [
    ('gate', 'close'), ('drain', 'stop'), ('backup', 'create'), ('backup', 'verify_after'),
    ('checks', 'migrated'), ('n', 'switch'), ('r', 'publish'), ('checks', 'frontend'),
    ('checks', 'first_scan'), ('n', 'verify'), ('s', 'installed'), ('gate', 'open_intake'),
])
def test_every_failure_closes_and_never_restores_old_database(release, monkeypatch, owner, name):
    *args, events = release
    def fail(*_):
        raise RuntimeError('injected')
    monkeypatch.setattr(getattr(d, owner), name, fail)
    with pytest.raises(RuntimeError, match='injected'):
        d.deploy(*args)
    work = args[0]
    assert (work / 'RECOVERY_REQUIRED.json').exists() and not (work / 'VERIFIED').exists()
    assert 'Never restore old DB' in (work / 'RECOVERY_REQUIRED.json').read_text()
    if (work / 'CLEANUP_MAY_HAVE_DELETED').exists():
        assert [e[1] for e in events if e[0] == 'pause-cleanup'] == [d.n.RETENTION, d.n.DELETE]
    assert not any(e[0] == 'compose' and ('down' in e or 'restart' in e) for e in events)


def test_started_cutover_cannot_be_replayed(release):
    work, *args, events = release
    (work / 'DEPLOY_STARTED').write_text('started')
    with pytest.raises(AssertionError, match='never replay'):
        d.deploy(work, *args)
    assert not events


def test_backup_must_be_restore_verified(release, monkeypatch):
    *args, events = release
    monkeypatch.setattr(d.backup, 'create', lambda *args: None)
    with pytest.raises(AssertionError):
        d.deploy(*args)
    assert not any(e[:2] == ('compose', 'run') for e in events)
