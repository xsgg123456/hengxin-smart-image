import copy
import importlib.util
import json
from pathlib import Path

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


p = module('package-record-filters')
d = module('domestic-record-filters-deploy')
v = module('domestic-record-filters-verify')
s = d.s
RELEASE = 'domestic-record-filters-20261022-abcdef0'


def valid_package():
    return {**{name: b'' for name in p.REQUIRED}, 'frontend/package.json': b'{"version":"0.2.49"}',
        'frontend/dist/index.html': b'<script src="/assets/main.js"></script>',
        'frontend/dist/assets/main.js': b'console.log(1)'}


def test_package_versions_schema_and_runtime_dependencies():
    p.validate(valid_package())
    assert p.package.VERSION == '0.2.49'
    assert p.package.DOMESTIC_MIGRATION == '0032'
    assert p.package.OVERSEAS_MIGRATION == 'overseas_0020'
    assert p.package.RELEASE_PREFIX == 'domestic-record-filters-20261022-'
    assert 'package-record-filters.py' in p.package.PACKAGING_HELPERS
    for name in p.REQUIRED:
        source = name if name.startswith('scripts/') else p.APP + name
        if not name.startswith('frontend/dist/'):
            assert p.selected(source) == name


@pytest.mark.parametrize('name', sorted(p.SCRIPTS) + ['test_api_image_records.py', 'test_api_image_records_pg.py'])
def test_missing_release_helpers_and_installation_tests_rejected(name):
    files = valid_package()
    key = ('backend/tests/' if name.startswith('test_') else 'scripts/release/') + name
    del files[key]
    with pytest.raises(ValueError, match='Missing'):
        p.validate(files)


@pytest.mark.parametrize('name', sorted(name for name in p.REQUIRED if '/cleanup_' in name or '/test_cleanup_' in name))
def test_missing_shared_cleanup_modules_or_regression_tests_rejected(name):
    files = valid_package()
    del files[name]
    with pytest.raises(ValueError, match='Missing record filters'):
        p.validate(files)


@pytest.mark.parametrize('path', ['frontend/preview-records-scope/index.html', 'backend/.env', 'backend/private.db'])
def test_preview_and_private_files_not_selected(path):
    assert p.selected(p.APP + path) is None


def test_wrong_version_and_preview_rejected():
    files = valid_package()
    files['frontend/package.json'] = b'{"version":"0.2.48"}'
    with pytest.raises(ValueError, match='version'):
        p.validate(files)
    files = valid_package()
    files['frontend/dist/preview-records-scope/index.html'] = b'preview'
    with pytest.raises(ValueError, match='preview'):
        p.validate(files)


@pytest.mark.parametrize('field,value', [('migration', '0031'), ('overseasMigration', 'overseas_0019'),
                                      ('frontendVersion', '0.2.48')])
def test_runtime_refuses_stale_manifest(tmp_path, monkeypatch, field, value):
    manifest = dict(release=RELEASE, frontendVersion='0.2.49', migration='0032',
        overseasMigration='overseas_0020', files={'backend/app/modules/api_image_edits/listing.py': 'hash'})
    manifest[field] = value
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src/release.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(s.r, 'hashes', lambda *_: pytest.fail('Must reject before hashing'))
    with pytest.raises(AssertionError):
        s.validate(tmp_path, RELEASE)


def test_overlay_only_allows_api_image():
    old = {'services': {'api': {'image': 'old', 'build': {'context': '/original'},
            'environment': {'POLICY': 'unchanged'}, 'stop_grace_period': '11m0s'},
        'api-image-worker': {'image': 'pinned-worker'}}}
    new = copy.deepcopy(old)
    new['services']['api']['image'] = 'candidate'
    s.same_settings(old, new)
    for service, key, value in [('api', 'environment', {}), ('api', 'build', {}),
            ('api', 'stop_grace_period', '30s'), ('api-image-worker', 'image', 'candidate')]:
        changed = copy.deepcopy(new)
        changed['services'][service][key] = value
        with pytest.raises(AssertionError):
            s.same_settings(old, changed)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value))


@pytest.fixture
def cutover(tmp_path, monkeypatch):
    events = []
    data = {'domestic': {'project': 'domestic'}}
    save(tmp_path / 'PREPARED', 'candidate')
    save(tmp_path / 'topology.json', data)
    save(tmp_path / 'domestic-compose.private.json', {})
    monkeypatch.setattr(d, 'BACKUPS', tmp_path / 'backup')
    monkeypatch.setattr(d.m, 'APP', tmp_path / 'app')
    monkeypatch.setattr(d.m, 'private', save)
    monkeypatch.setattr(d.m, 'image_id', lambda *_: 'candidate')
    monkeypatch.setattr(d.s, 'topology', lambda: data)
    monkeypatch.setattr(d.s, 'baseline', lambda: None)
    monkeypatch.setattr(d.s, 'same_settings', lambda *_: None)
    monkeypatch.setattr(d.m, 'assets_safe', lambda *_: None)
    monkeypatch.setattr(d.m, 'run', lambda *args, **kw: events.append(('run', *args)))
    def compose(_data, *args, **kw):
        events.append(('compose', *args))
        return '{}' if args[0] == 'config' else ''
    monkeypatch.setattr(d.m, 'compose', compose)
    def sql(query):
        events.append(('sql', query))
        return 'f' if query.startswith('SELECT paused') else '0'
    monkeypatch.setattr(d.r, 'sql', sql)
    def backup(work, destination, *_):
        events.append(('backup',))
        destination.mkdir(parents=True)
        (destination / 'COMPLETE').write_text('yes')
    monkeypatch.setattr(d.checks, 'backup', backup)
    for owner, name in ((d.gate, 'close'), (d.gate, 'verify_closed'), (d.gate, 'open_intake'),
        (d.s.p, 'graceful_stop'), (d.drain, 'stop'), (d.checks, 'preserved'),
        (d.checks, 'routes'), (d.checks, 'frontend'), (d.n, 'ready'), (d.s, 'schemas'),
        (d.s, 'start_existing'), (d.s, 'installed'), (d.r, 'publish'), (d.r, 'worker'),
        (d.cleanup, 'mark_start'), (d.cleanup, 'first_scan'), (d.s.p.base, 'public_verify'),
        (d.n, 'switch'), (d.n.old, 'stop')):
        monkeypatch.setattr(owner, name, lambda *args, label=name: events.append((label, *args)))
    return tmp_path, tmp_path / 'src', {'release': RELEASE}, 'image', events


def test_api_and_native_switch_no_migration_or_policy_writes(cutover):
    *args, events = cutover
    d.deploy(*args)
    changes = [event for event in events if event[:2] == ('compose', 'up')]
    assert len(changes) == 1 and changes[0][-1] == 'api'
    assert '--no-build' in changes[0] and '--no-deps' in changes[0]
    assert not any(event[:2] == ('compose', 'run') for event in events)
    writes = [event[1] for event in events if event[0] == 'sql' and event[1].startswith('UPDATE')]
    assert writes == ['UPDATE api_image_channel SET paused=true WHERE id=1',
                      'UPDATE api_image_channel SET paused=false WHERE id=1']
    labels = [event[0] for event in events]
    assert labels.index('stop') < labels.index('backup') < labels.index('preserved') < events.index(changes[0])
    assert labels.index('backup') < labels.index('switch') < events.index(changes[0])
    assert labels.index('switch') < labels.index('start_existing')
    assert labels.index('routes') < labels.index('publish') < labels.index('start_existing')
    assert labels.index('first_scan') < labels.index('open_intake')
    assert [event[-1] for event in events if event[0] == 'start_existing'] == [s.CONSUMERS, s.PRODUCERS]
    assert (args[0] / 'VERIFIED').exists()


@pytest.mark.parametrize('owner,name', [('gate', 'close'), ('drain', 'stop'), ('checks', 'backup'),
    ('checks', 'preserved'), ('checks', 'routes'), ('r', 'publish'), ('checks', 'frontend'),
    ('n', 'ready'), ('cleanup', 'first_scan'), ('s', 'start_existing'), ('s', 'installed'),
    ('gate', 'open_intake'), ('n', 'switch')])
def test_failure_keeps_intake_closed_and_never_restores_db(cutover, monkeypatch, owner, name):
    *args, events = cutover
    def fail(*_):
        raise RuntimeError('injected')
    monkeypatch.setattr(getattr(d, owner), name, fail)
    with pytest.raises(RuntimeError, match='injected'):
        d.deploy(*args)
    work = args[0]
    assert (work / 'RECOVERY_REQUIRED.json').exists() and not (work / 'VERIFIED').exists()
    assert 'Never restore old DB' in (work / 'RECOVERY_REQUIRED.json').read_text()
    assert ('sql', 'UPDATE api_image_channel SET paused=true WHERE id=1') in events
    assert events[-2:] == [('stop', d.n.DELETE), ('stop', d.n.RETENTION)]
    assert not any(event[0] == 'compose' and ('down' in event or 'restart' in event) for event in events)


def test_cannot_replay_started_cutover(cutover):
    work, *args, events = cutover
    save(work / 'DEPLOY_STARTED', 'started')
    with pytest.raises(AssertionError, match='never replay'):
        d.deploy(work, *args)
    assert not events


def test_early_failure_stops_each_cleanup_even_when_first_stop_fails(cutover, monkeypatch):
    *args, events = cutover
    work = args[0]
    def fail(*_):
        raise RuntimeError('api stop failed')
    def stop(unit):
        events.append(('stop', unit))
        if unit == d.n.DELETE:
            raise TimeoutError('still stopping')
    monkeypatch.setattr(d.s.p, 'graceful_stop', fail)
    monkeypatch.setattr(d.n.old, 'stop', stop)
    with pytest.raises(RuntimeError, match='api stop failed'):
        d.deploy(*args)
    assert not (work / 'CLEANUP_MAY_HAVE_DELETED').exists()
    assert events[-2:] == [('stop', d.n.DELETE), ('stop', d.n.RETENTION)]
    assert (work / (d.n.DELETE + '.STOP_REQUIRED')).read_text() == 'TimeoutError'
    assert not (work / (d.n.RETENTION + '.STOP_REQUIRED')).exists()


def test_unverified_backup_cannot_switch(cutover, monkeypatch):
    *args, events = cutover
    monkeypatch.setattr(d.checks, 'backup', lambda *_: None)
    with pytest.raises(AssertionError):
        d.deploy(*args)
    assert not any(event[:2] == ('compose', 'up') for event in events)
    assert not any(event[0] == 'switch' for event in events)


def test_cleanup_start_marker_precedes_process_start_and_stop_failure_is_recorded(cutover, monkeypatch):
    *args, events = cutover
    work = args[0]
    def run(*command, **kw):
        if d.n.DELETE in command:
            assert (work / 'CLEANUP_MAY_HAVE_DELETED').exists()
        events.append(('run', *command))
    def failed_scan(*_):
        raise RuntimeError('scan failure')
    def stop(unit):
        events.append(('stop', unit))
        if unit == d.n.DELETE:
            raise TimeoutError('still busy')
    monkeypatch.setattr(d.m, 'run', run)
    monkeypatch.setattr(d.cleanup, 'first_scan', failed_scan)
    monkeypatch.setattr(d.n.old, 'stop', stop)
    with pytest.raises(RuntimeError, match='scan failure'):
        d.deploy(*args)
    assert (work / (d.n.DELETE + '.STOP_REQUIRED')).read_text() == 'TimeoutError'
    assert events[-1] == ('stop', d.n.RETENTION)
    assert json.loads((work / 'RECOVERY_REQUIRED.json').read_text())['phase'] == 'resume-consumers'


def test_existing_services_start_same_container_and_image(monkeypatch):
    events = []
    name = s.m.container('domestic', 'api-image-worker')
    data = {'domestic': {'ids': {name: 'id'}}, 'images': {'domestic': {name: 'sha:worker'}}}
    monkeypatch.setattr(s.m, 'live', lambda _: {'Id': 'id', 'Image': 'sha:worker'})
    monkeypatch.setattr(s.m, 'run', lambda *args: events.append(args))
    s.start_existing(data, ['api-image-worker'])
    assert events == [('docker', 'start', name)]
    monkeypatch.setattr(s.m, 'live', lambda _: {'Id': 'replacement', 'Image': 'sha:worker'})
    with pytest.raises(AssertionError):
        s.start_existing(data, ['api-image-worker'])
    assert len(events) == 1


def test_managed_entrypoint_and_network_isolated_install_tests():
    entry = Path(d.__file__).read_text()
    assert "m.module('release-retention').managed(main)" in entry
    build = Path(__file__).with_name('overseas-deploy.py').read_text()
    assert "'--network', 'none'" in build
    assert 'INSTALL_TEST_IMAGE_ID' in build and 'IMAGE_SOURCE_HASHES' in build
    assert 'test_api_image_records' not in build.split('ignored =', 1)[1].split('args =', 1)[0]
