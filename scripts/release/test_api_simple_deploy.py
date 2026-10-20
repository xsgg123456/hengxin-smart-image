import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('simple_deploy', Path(__file__).with_name('api-simple-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
RELEASE = 'domestic-api-simple-20261020-abcdef0'


@pytest.fixture
def release(monkeypatch, tmp_path):
    events = []
    data = {'domestic': {'project': 'domestic'}}
    (tmp_path / 'PREPARED').write_text('sha256:candidate')
    (tmp_path / 'topology.json').write_text(json.dumps(data))
    (tmp_path / 'domestic-compose.private.json').write_text('{}')
    source = tmp_path / 'source'
    (source / 'frontend').mkdir(parents=True)
    (source / 'frontend/package.json').write_text('{"version":"0.2.45"}')
    monkeypatch.setattr(d.m, 'APP', source)
    monkeypatch.setattr(d, 'BACKUPS', tmp_path / 'backup')
    monkeypatch.setattr(d.m, 'image_id', lambda *_: 'sha256:candidate')
    monkeypatch.setattr(d.m, 'live', lambda *_: {'State': {'Running': False}})
    monkeypatch.setattr(d, 'topology', lambda: data)
    monkeypatch.setattr(d, 'baseline', lambda: None)
    monkeypatch.setattr(d, 'same_settings', lambda *_: None)
    monkeypatch.setattr(d.m, 'assets_safe', lambda *_: None)
    monkeypatch.setattr(d.m, 'private', lambda path, value: events.append(('save', path.name, value)))
    def compose(_data, *args, **kw):
        events.append(('compose', *args))
        return '{}' if args[0] == 'config' else ''
    monkeypatch.setattr(d.m, 'compose', compose)
    def sql(query):
        if query.startswith('SELECT paused'): return 'f'
        events.append(('sql', query))
        return '0031'
    monkeypatch.setattr(d.r, 'sql', sql)
    def backup(work, destination, *_):
        events.append(('backup',))
        destination.mkdir(parents=True)
        (destination / 'protected.json').write_text('{}')
    monkeypatch.setattr(d, 'backup', backup)
    for owner, name in ((d.gate, 'close'), (d.gate, 'verify_closed'), (d.gate, 'open_intake'),
                        (d, 'graceful_stop'), (d.handoff, 'drain'), (d.handoff, 'wait_idle'),
                        (d.handoff, 'verify_protected'), (d, 'verify_preserved'), (d, 'verify'),
                        (d, 'unchanged'), (d.r, 'publish'), (d.previous.base, 'public_verify')):
        monkeypatch.setattr(owner, name, lambda *args, label=name: events.append((label, *args)))
    return tmp_path, source, {'release': RELEASE}, 'image', events


def test_cutover_uses_staged_three_service_handoff_without_migration(release):
    *args, events = release
    d.deploy(*args)
    labels = [row[0] for row in events]
    pause = next(i for i, row in enumerate(events) if row[0] == 'sql' and 'paused=true' in row[1])
    assert labels.index('close') < labels.index('graceful_stop') < pause < labels.index('drain')
    assert labels.index('drain') < labels.index('backup') < labels.index('verify_preserved')
    switches = [row for row in events if row[:2] == ('compose', 'up')]
    assert len(switches) == 2
    assert switches[0][-2:] == ('api', 'api-image-worker')
    assert switches[1][-1] == 'api-image-outbox'
    assert labels.count('verify_preserved') == 2
    last_preserved = max(i for i, row in enumerate(events) if row[0] == 'verify_preserved')
    assert events.index(switches[0]) < labels.index('wait_idle') < last_preserved < events.index(switches[1])
    assert not any(row[0] == 'compose' and 'migrate' in row for row in events)
    assert labels.index('verify') < labels.index('verify_protected') < labels.index('publish') < labels.index('open_intake')
    assert not any('systemctl' in row for row in events)


@pytest.mark.parametrize('owner_name,failure', [
    ('gate', 'close'), ('handoff', 'drain'), ('self', 'backup'), ('self', 'verify_preserved'),
    ('handoff', 'wait_idle'), ('self', 'verify'), ('handoff', 'verify_protected'),
    ('r', 'publish'), ('gate', 'open_intake'), ('public', 'public_verify'),
])
def test_failures_close_intake_without_restoring_or_restarting_old_code(release, monkeypatch, owner_name, failure):
    *args, events = release
    owner = {'self': d, 'public': d.previous.base}.get(owner_name, getattr(d, owner_name, None))
    def fail(*_):
        events.append(('injected', failure))
        raise RuntimeError('injected')
    monkeypatch.setattr(owner, failure, fail)
    with pytest.raises(RuntimeError, match='injected'):
        d.deploy(*args)
    assert any(row[:2] == ('save', 'RECOVERY_REQUIRED.json') for row in events)
    if failure == 'close':
        assert events[-1][:2] == ('save', 'GATE_RECOVERY_REQUIRED')
    else:
        assert events[-1][0] == 'close'
    assert not any(row[0] == 'compose' and any(x in row for x in ('restart', 'down', 'migrate')) for row in events)


def test_schema_and_all_api_columns_preserve_nonzero_cycles(monkeypatch, tmp_path):
    projection = {'api_image_items': ['id', 'retry_cycle_id', 'retry_policy_version']}
    (tmp_path / 'columns.json').write_text(json.dumps(projection))
    (tmp_path / 'fingerprints.json').write_text('{"api_image_items":"97:hash"}')
    (tmp_path / 'retry-cycles.json').write_text('97')
    monkeypatch.setattr(d.r, 'sql', lambda _: '0031')
    monkeypatch.setattr(d, 'columns', lambda _: projection)
    monkeypatch.setattr(d, 'fingerprints', lambda *_: {'api_image_items': '97:hash'})
    monkeypatch.setattr(d, 'cycles', lambda: 97)
    d.verify_preserved(tmp_path)
    monkeypatch.setattr(d, 'cycles', lambda: 0)
    with pytest.raises(AssertionError, match='cycles changed'):
        d.verify_preserved(tmp_path)
    monkeypatch.setattr(d, 'cycles', lambda: 97)
    monkeypatch.setattr(d, 'fingerprints', lambda *_: {'api_image_items': '97:different'})
    with pytest.raises(AssertionError, match='rows changed'):
        d.verify_preserved(tmp_path)
    monkeypatch.setattr(d, 'columns', lambda _: {'api_image_items': ['id']})
    with pytest.raises(AssertionError, match='columns changed'):
        d.verify_preserved(tmp_path)


@pytest.mark.parametrize('schema,frontend,valid', [
    ('0031', '0.2.44', True), ('0030', '0.2.44', False), ('0031', '0.2.43', False),
])
def test_only_observed_0031_baseline_is_accepted(monkeypatch, tmp_path, schema, frontend, valid):
    (tmp_path / 'frontend').mkdir()
    (tmp_path / 'frontend/package.json').write_text(json.dumps({'version': frontend}))
    monkeypatch.setattr(d.m, 'APP', tmp_path)
    monkeypatch.setattr(d.r, 'sql', lambda _: schema)
    monkeypatch.setattr(d.m.u, 'sql', lambda _: 'overseas_0019')
    if valid:
        d.baseline()
    else:
        with pytest.raises(AssertionError):
            d.baseline()


def test_overlay_allows_only_three_api_images():
    old = {'services': {name: {'image': 'old', 'environment': {'SETTING': 'retained'}}
                        for name in (*d.SERVICES, 'migrate', 'outbox')}}
    new = json.loads(json.dumps(old))
    for name in d.SERVICES:
        new['services'][name]['image'] = 'new'
    d.same_settings(old, new)
    for service, field, value in [('migrate', 'image', 'new'), ('outbox', 'image', 'new'),
                                  ('api', 'environment', {})]:
        changed = json.loads(json.dumps(new))
        changed['services'][service][field] = value
        with pytest.raises(AssertionError):
            d.same_settings(old, changed)


def test_build_uses_real_existing_image_installation_pipeline(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(sys, 'argv', ['api-simple-deploy.py', RELEASE, 'build'])
    monkeypatch.setattr(d, 'validate', lambda *_: (tmp_path, {}, 'candidate-image'))
    monkeypatch.setattr(d.os, 'umask', lambda _: None)
    def module(name):
        assert name == 'overseas-deploy'
        return SimpleNamespace(build=lambda *args: events.append(args))
    monkeypatch.setattr(d.m, 'module', module)
    d.main()
    assert events == [(Path('/opt/hengxin-releases') / RELEASE, tmp_path, 'candidate-image')]
