import importlib.util
import json
from pathlib import Path

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v, b, s = (load('retention-management-' + name) for name in ('verify', 'backup', 'runtime'))


def observation(status='completed', fresh=True):
    return dict(heartbeatFresh=fresh, records=0, scan=dict(id='id', status=status,
        startedAt='2026-10-21T01:00:00+00:00', finishedAt='2026-10-21T01:00:01+00:00'))


def test_first_scan_requires_persisted_completion_and_fresh_heartbeat():
    assert v.completed(observation())
    assert not v.completed(observation('running'))
    assert not v.completed(observation(fresh=False))
    assert not v.completed(dict(heartbeatFresh=True, records=0, scan=None))
    for status in ('failed', 'unknown'):
        with pytest.raises(AssertionError):
            v.completed(observation(status))
    row = observation()
    row['scan']['finishedAt'] = None
    with pytest.raises(AssertionError):
        v.completed(row)


@pytest.mark.parametrize('started', ["2026-10-21';DROP TABLE cli_retention;--", '2026-10-21', None])
def test_scan_timestamp_rejects_injection_and_naive_time(started):
    with pytest.raises((AssertionError, ValueError)):
        v.observation_sql(started)


def test_first_scan_reads_real_database_and_checks_new_invocation(monkeypatch, tmp_path):
    (tmp_path / 'cleanup-start.json').write_text(json.dumps('2026-10-21T01:00:00+00:00'))
    events = []
    monkeypatch.setattr(v.n, 'show', lambda *_: 'invocation')
    def run(*args, **kw):
        events.append(args)
        return json.dumps(observation())
    monkeypatch.setattr(v.m, 'run', run)
    monkeypatch.setattr(v.m, 'private', lambda path, value: events.append(('save', path.name, value)))
    v.first_scan(tmp_path)
    assert 'cli_retention_runs' in events[0][-1] and 'heartbeat_at' in events[0][-1]
    assert events[-1][:2] == ('save', 'CLEANUP_READY')


def test_migration_rejects_fabricated_history(monkeypatch):
    monkeypatch.setattr(v.r, 'sql', lambda q: '1' if q.endswith('cli_retention_totals') else '0')
    v.migrated()
    monkeypatch.setattr(v.r, 'sql', lambda q: '1')
    with pytest.raises(AssertionError, match='fabricated'):
        v.migrated()


def test_only_0031_0245_baseline_accepted(monkeypatch, tmp_path):
    (tmp_path / 'frontend').mkdir()
    (tmp_path / 'frontend/package.json').write_text('{"version":"0.2.45"}')
    monkeypatch.setattr(s.m, 'APP', tmp_path)
    monkeypatch.setattr(s.r, 'sql', lambda _: '0031')
    monkeypatch.setattr(s.m.u, 'sql', lambda _: 'overseas_0019')
    s.baseline()
    monkeypatch.setattr(s.r, 'sql', lambda _: '0030')
    with pytest.raises(AssertionError):
        s.baseline()


def test_compose_allows_only_images_and_build_preserving_api_retry_settings():
    old = {'services': {name: {'image': 'old', 'environment': {'SEND': '5', 'AGE': '2700'},
                              'command': ['run'], 'stop_grace_period': '11m0s'}
                        for name in (*s.SERVICES, 'migrate', 'postgres')}}
    new = json.loads(json.dumps(old))
    for name in (*s.SERVICES, 'migrate'):
        new['services'][name]['image'] = 'new'
    s.same_settings(old, new)
    for name, field, value in [('api', 'environment', {}), ('outbox', 'command', ['different']),
        ('api-image-worker', 'stop_grace_period', '30s'), ('postgres', 'image', 'new')]:
        bad = json.loads(json.dumps(new))
        bad['services'][name][field] = value
        with pytest.raises(AssertionError):
            s.same_settings(old, bad)


def backup_state(tmp_path):
    before = {'api_image_items': '97:unchanged', 'cli_retention': '8:unchanged'}
    for name, value in {'fingerprints-preserved.json': before,
        'columns.json': {'api_image_items': ['id'], 'cli_retention': ['id', 'next_cleanup_at']},
        'expected-schedules.json': {'active': '2026-10-18T01:00:00+00:00', 'pending': '2026-10-21T02:00:00+00:00'}}.items():
        (tmp_path / name).write_text(json.dumps(value))
    (tmp_path / 'COMPLETE').write_text('yes')
    return before


@pytest.mark.parametrize('mutation', [None, 'row', 'table', 'column', 'barrier'])
def test_migration_preserves_business_rows_schema_and_exact_pending_schedule(monkeypatch, tmp_path, mutation):
    before = backup_state(tmp_path)
    after = {**before, **{name: '0:empty' for name in v.ADDED}}
    columns = json.loads((tmp_path / 'columns.json').read_text())
    schedules = json.loads((tmp_path / 'expected-schedules.json').read_text())
    if mutation == 'row': after['api_image_items'] = '97:changed'
    if mutation == 'table': del after['cli_retention_runs']
    if mutation == 'column': columns['api_image_items'].append('unexpected')
    if mutation == 'barrier': schedules['pending'] = '2026-10-21T00:00:00+00:00'
    monkeypatch.setattr(b, 'fingerprint', lambda *_: after)
    monkeypatch.setattr(b.p, 'columns', lambda *_: columns)
    monkeypatch.setattr(b.b, 'query', lambda *_: json.dumps(schedules))
    monkeypatch.setattr(b.m, 'private', lambda *args: None)
    if mutation:
        with pytest.raises(AssertionError):
            b.verify_after(tmp_path, v.ADDED)
    else:
        b.verify_after(tmp_path, v.ADDED)


def test_expected_schedule_only_reschedules_active_api_cli():
    assert "domain='api_cli' AND status='active'" in b.SCHEDULE
    assert "interval '24 hours'" in b.SCHEDULE and "interval '72 hours'" in b.SCHEDULE
    assert 'ELSE next_cleanup_at' in b.SCHEDULE


def test_backup_restore_failure_cannot_write_complete(monkeypatch, tmp_path):
    work, destination = tmp_path / 'work', tmp_path / 'backup'
    work.mkdir()
    for name in ('EXECUTORS_STOPPED', 'CLEANUP_STOPPED', 'edge-before.conf', 'web-before.conf',
                 'domestic-compose.private.json', 'native-snapshots.private.json'):
        (work / name).write_text('data')
    original = b.b.fingerprint
    monkeypatch.setattr(b.m, 'APP', tmp_path / 'app')
    monkeypatch.setattr(b.m, 'private', lambda path, value: path.write_text(str(value)))
    monkeypatch.setattr(b, 'fingerprint', lambda *_: {'rows': 'stable'})
    monkeypatch.setattr(b.p, 'columns', lambda *_: {})
    monkeypatch.setattr(b.b, 'query', lambda *_: '{}')
    monkeypatch.setattr(b.b, 'dump', lambda *_: None)
    def fail(*_):
        raise RuntimeError('restore failed')
    monkeypatch.setattr(b.b, 'restore_check', fail)
    with pytest.raises(RuntimeError, match='restore failed'):
        b.create(work, destination, {'domestic': {'files': {}}, 'nativeFiles': {}}, 'release')
    assert not (destination / 'COMPLETE').exists()
    assert b.b.fingerprint is original
