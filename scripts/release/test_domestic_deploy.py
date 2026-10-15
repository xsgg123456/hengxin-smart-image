import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('domestic_deploy', Path(__file__).with_name('domestic-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


@pytest.fixture
def release(monkeypatch, tmp_path):
    events = []
    source = tmp_path / 'src'
    (source / 'frontend').mkdir(parents=True)
    (source / 'frontend/package.json').write_text('{"version":"0.2.37"}')
    data = {'domestic': {'project': 'domestic'}, 'native': {}}
    for name, value in [('topology.json', data), ('native-policy.json', {}),
                        ('domestic-compose.private.json', {})]:
        (tmp_path / name).write_text(json.dumps(value))
    (tmp_path / 'PREPARED').write_text('sha256:image')
    monkeypatch.setattr(d.m, 'APP', source)
    monkeypatch.setattr(d.m, 'topology', lambda: data)
    monkeypatch.setattr(d.m, 'image_id', lambda *_: 'sha256:image')
    monkeypatch.setattr(d.m, 'assets_safe', lambda *_: None)
    monkeypatch.setattr(d.m, 'same_settings', lambda *_: None)
    monkeypatch.setattr(d.m, 'private', lambda path, value: events.append(('save', path.name, value)))
    monkeypatch.setattr(d.m, 'run', lambda *args, **kw: events.append(('run', *args)) or '')
    monkeypatch.setattr(d.n, 'native_policy', lambda: {})
    monkeypatch.setattr(d.n, 'switch_native', lambda *_: events.append(('switch',)))
    monkeypatch.setattr(d.n, 'unchanged_other_groups', lambda *_: events.append(('other-unchanged',)))

    def compose(_data, *args, **kw):
        events.append(('compose', *args))
        return '{}' if args[0] == 'config' else ''

    def sql(statement):
        if statement.startswith('SELECT version_num'):
            return '0029' if any(row[:2] == ('compose', 'run') for row in events) else '0028'
        if statement.startswith('SELECT paused'):
            return 'f'
        events.append(('sql', statement))
        return ''

    monkeypatch.setattr(d.m, 'compose', compose)
    monkeypatch.setattr(d.r, 'sql', sql)
    monkeypatch.setattr(d.r, 'publish', lambda *_: events.append(('publish',)))
    monkeypatch.setattr(d.gate, 'close', lambda *_: events.append(('close',)))
    monkeypatch.setattr(d.gate, 'verify_closed', lambda: events.append(('closed-verified',)))
    monkeypatch.setattr(d.gate, 'open_intake', lambda *_: events.append(('open',)))
    monkeypatch.setattr(d.drain, 'stop', lambda *_: events.append(('drained',)))
    monkeypatch.setattr(d.backup, 'create', lambda *_: events.append(('backup-restored',)))
    monkeypatch.setattr(d.backup, 'verify_after', lambda *_: events.append(('rows-preserved',)))
    monkeypatch.setattr(d, 'verify', lambda *_: events.append(('installed-verified',)))
    monkeypatch.setattr(d, 'public_verify', lambda *_: events.append(('public-verified',)))
    manifest = {'release': 'domestic-20261015-abcdef0'}
    return tmp_path, source, manifest, 'image', events


def test_cutover_order_and_domestic_only_scope(release):
    *args, events = release
    d.deploy(*args)
    names = [row[0] for row in events]
    assert names.index('close') < names.index('drained') < names.index('backup-restored')
    assert names.index('backup-restored') < names.index('rows-preserved') < names.index('switch')
    assert names.index('installed-verified') < names.index('publish') < names.index('open') < names.index('public-verified')
    commands = [row for row in events if row[0] in ('run', 'compose')]
    assert not any('identity-api' in row or 'overseas' in row or 'web' in row for row in commands)
    assert any(row == ('run', 'systemctl', 'enable', '--now', 'hengxin-domestic-deletions') for row in commands)


@pytest.mark.parametrize('failure', ['drain', 'backup', 'verify', 'public'])
def test_failure_keeps_intake_closed_and_never_blindly_stops_workers(release, monkeypatch, failure):
    *args, events = release

    def fail(*_):
        raise RuntimeError('fault injected')

    owner, name = {'drain': (d.drain, 'stop'), 'backup': (d.backup, 'create'),
                   'verify': (d, 'verify'), 'public': (d, 'public_verify')}[failure]
    monkeypatch.setattr(owner, name, fail)
    with pytest.raises(RuntimeError, match='fault injected'):
        d.deploy(*args)
    assert events[-1] == ('close',)
    assert any(row[:2] == ('save', 'RECOVERY_REQUIRED.json') for row in events)
    stops = [row for row in events if row[0] in ('run', 'compose') and 'stop' in row]
    assert stops == [('compose', 'stop', '-t', '30', 'api')]
    assert not any(row[:2] == ('save', 'VERIFIED') for row in events)


def test_prepare_drift_fails_before_intake_mutation(release, monkeypatch):
    *args, events = release
    monkeypatch.setattr(d.m, 'topology', lambda: {'changed': True})
    with pytest.raises(AssertionError, match='topology changed'):
        d.deploy(*args)
    assert not events


def test_cli_uses_managed_retention_wrapper():
    text = Path(d.__file__).read_text()
    assert "m.module('release-retention').managed(main)" in text
    assert "m.module('overseas-deploy').build(work, source, image)" in text
    assert 'overseas-deploy.py' not in text
