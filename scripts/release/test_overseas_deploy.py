"""Fault injection for cutover ordering; no process, network or production writes."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

spec = importlib.util.spec_from_file_location('overseas_deploy', Path(__file__).with_name('overseas-deploy.py'))
d = importlib.util.module_from_spec(spec)
# Server-only pwd is never invoked in these platform-independent fault tests.
with patch.dict(sys.modules, {'pwd': Mock()}):
    spec.loader.exec_module(d)


@pytest.fixture
def cutover(monkeypatch, tmp_path):
    work = tmp_path / 'release'
    work.mkdir()
    source = work / 'src'
    source.mkdir()
    app = tmp_path / 'application'
    (app / 'infra').mkdir(parents=True)
    release = 'overseas-20261013-abcdef0'
    manifest = {'release': release}
    paths = ['/opt/existing/compose.yaml']
    (work / 'PREPARED').write_text('ready')
    (work / 'INSTALL_TEST_IMAGE_ID').write_text('sha256:verified')
    (work / 'old-paths.json').write_text(json.dumps(paths))
    (work / 'native-target').write_text(str(tmp_path / 'native'))
    events = []
    state = SimpleNamespace(fail=None, migrated=False, pending=[0], image='sha256:verified')

    def emit(kind, *args):
        events.append((kind, *args))

    def path(value):
        value = str(value)
        if value.startswith(('/opt/', '/etc/')):
            return tmp_path / 'server' / value.lstrip('/')
        return Path(value)

    def run(*args, **kwargs):
        emit('run', *args)
        if args[:3] == ('docker', 'image', 'inspect'):
            return state.image
        if state.fail == 'public-check' and args[0] == 'python3' and args[-1] == release:
            raise RuntimeError('public verification failed')
        return ''

    def compose(configs, *args, **kwargs):
        emit('compose', tuple(configs), *args)
        if args[:3] == ('run', '--rm', '--no-deps'):
            if state.fail == 'migration':
                raise RuntimeError('migration failed')
            state.migrated = True
        if state.fail == 'web-open' and args == ('up', '-d', '--no-deps', '--wait', 'web'):
            raise RuntimeError('web start outcome unknown')

    def sql(query):
        emit('sql', query)
        if query.startswith('SELECT paused'):
            return 'f'
        if query.startswith('SELECT version_num'):
            return '0027' if state.migrated else '0026'
        return ''

    def pending():
        result = state.pending.pop(0) if len(state.pending) > 1 else state.pending[0]
        emit('pending', result)
        return result

    def backup(_work, destination, _paths):
        emit('backup')
        if state.fail == 'backup':
            raise RuntimeError('backup failed')
        destination.mkdir(parents=True)
        (destination / 'baseline.json').write_text(json.dumps({'schema': '0026', 'users': '2:hash'}))
        (destination / 'COMPLETE').write_text('complete')

    def worker(_helper, mode):
        emit('worker', mode)

    def install_edge():
        emit('install_edge')
        if state.fail == 'install-edge':
            raise RuntimeError('edge installation failed')

    fake = SimpleNamespace(APP=app, PREFIX='test-', SERVICES=d.r.SERVICES,
        run=run, compose=compose, sql=sql, pending=pending, backup=backup, worker=worker,
        switch_native=lambda *_: emit('switch_native'), ready=lambda: emit('ready'),
        baseline=lambda: {'schema': '0027', 'users': '2:hash'},
        proxy_config=lambda: 'safe nginx', publish=lambda *_: emit('publish'), install_edge=install_edge,
        restore_front=lambda *_: emit('restore_front'), private=lambda *_: emit('private'))
    monkeypatch.setattr(d, 'r', fake)
    monkeypatch.setattr(d, 'Path', path)
    monkeypatch.setattr(d.s, 'setup', Mock(side_effect=AssertionError('unexpected setup')))
    return SimpleNamespace(work=work, source=source, manifest=manifest, release=release,
                           image='hengxin-smart-image-backend:' + release,
                           paths=paths, events=events, state=state)


def stops(events):
    return [e for e in events if e[0] == 'compose' and e[2] == 'stop']


def test_pending_work_defers_before_any_service_stop(cutover):
    c = cutover
    c.state.pending = [1]
    with pytest.raises(AssertionError, match='In-flight'):
        d.deploy(c.work, c.source, c.manifest)
    assert not stops(c.events)
    assert not any(e[0] in ('worker', 'backup', 'switch_native', 'publish') for e in c.events)
    assert not any(e[0] == 'sql' and e[1].startswith('UPDATE') for e in c.events)


def test_work_found_after_intake_closes_preserves_executors(cutover):
    c = cutover
    c.state.pending = [0, 1]
    with pytest.raises(AssertionError):
        d.deploy(c.work, c.source, c.manifest)
    assert stops(c.events)
    assert all('api-image-worker' not in e and 'image-variants' not in e for e in stops(c.events))
    assert ('worker', 'native-stop') not in c.events
    assert not any(e[0] in ('backup', 'restore_front', 'switch_native') for e in c.events)
    assert ('sql', 'UPDATE api_image_channel SET paused=false WHERE id=1') not in c.events


@pytest.mark.parametrize('failure', ['backup', 'migration'])
def test_pre_switch_failure_after_drain_restores_old_services(cutover, failure):
    c = cutover
    c.state.fail = failure
    with pytest.raises(RuntimeError, match=failure):
        d.deploy(c.work, c.source, c.manifest)
    assert c.events.index(('worker', 'api-drain')) < c.events.index(('worker', 'native-stop')) < c.events.index(('backup',))
    old_up = ('compose', tuple(c.paths), 'up', '-d', '--no-deps', '--wait', *d.r.SERVICES)
    web_up = ('compose', tuple(c.paths), 'up', '-d', '--no-deps', '--wait', 'web')
    assert old_up in c.events and web_up in c.events
    assert ('run', 'systemctl', 'start', 'hengxin-vps-codex-worker') in c.events
    assert ('worker', 'native-verify') in c.events
    assert ('worker', 'api-verify') in c.events
    assert c.events.index(old_up) < c.events.index(('sql', 'UPDATE api_image_channel SET paused=false WHERE id=1')) < c.events.index(web_up)
    assert ('switch_native',) not in c.events
    assert (('restore_front',) in c.events) == (failure == 'migration')


@pytest.mark.parametrize('failure', ['web-open', 'public-check'])
def test_failure_after_opening_only_closes_intake(cutover, failure):
    c = cutover
    c.state.fail = failure
    with pytest.raises(RuntimeError):
        d.deploy(c.work, c.source, c.manifest)
    open_index = next(i for i, e in enumerate(c.events)
                      if e[0] == 'compose' and e[2:] == ('up', '-d', '--no-deps', '--wait', 'web'))
    recovery = c.events[open_index + 1:]
    assert len(stops(recovery)) == 1
    assert stops(recovery)[0][2:] == ('stop', '-t', '30', 'web', 'api', 'outbox', 'api-image-outbox')
    assert ('sql', 'UPDATE api_image_channel SET paused=true WHERE id=1') in recovery
    assert not any(e[0] in ('worker', 'restore_front', 'switch_native', 'publish', 'private') for e in recovery)
    assert not any(e[0] == 'compose' and e[2] == 'up' for e in recovery)
    assert ('sql', 'UPDATE api_image_channel SET paused=false WHERE id=1') not in recovery
    assert not any(e[0] == 'run' and e[1] == 'systemctl' for e in recovery)


def test_edge_install_failure_drains_new_executors_before_old_services_restore(cutover):
    c = cutover
    c.state.fail = 'install-edge'
    with pytest.raises(RuntimeError, match='edge installation failed'):
        d.deploy(c.work, c.source, c.manifest)
    recovery = c.events[c.events.index(('install_edge',)) + 1:]
    old_up = ('compose', tuple(c.paths), 'up', '-d', '--no-deps', '--wait', *d.r.SERVICES)
    web_up = ('compose', tuple(c.paths), 'up', '-d', '--no-deps', '--wait', 'web')
    executor_stop = next(e for e in stops(recovery) if 'api-image-worker' in e)
    assert recovery.index(('pending', 0)) < recovery.index(('worker', 'api-drain'))
    assert recovery.index(('worker', 'api-drain')) < recovery.index(executor_stop)
    assert recovery.index(executor_stop) < recovery.index(('worker', 'native-stop'))
    assert recovery.index(('worker', 'native-stop')) < recovery.index(('restore_front',)) < recovery.index(old_up)
    assert recovery.index(old_up) < recovery.index(('worker', 'api-verify'))
    assert recovery.index(('worker', 'api-verify')) < recovery.index(('sql', 'UPDATE api_image_channel SET paused=false WHERE id=1')) < recovery.index(web_up)
    assert ('run', 'systemctl', 'daemon-reload') in recovery
    assert not any(e[0] == 'private' for e in recovery)


@pytest.mark.parametrize('action', ['prepare', 'deploy'])
def test_changed_installation_image_blocks_prepare_and_deploy(cutover, action):
    c = cutover
    c.state.image = 'sha256:unverified'
    with pytest.raises(AssertionError):
        if action == 'prepare':
            d.prepare(c.work, c.source, c.image, c.release)
        else:
            d.deploy(c.work, c.source, c.manifest)
    assert len(c.events) == 1
    assert c.events[0][:4] == ('run', 'docker', 'image', 'inspect')
    d.s.setup.assert_not_called()


def test_build_blocks_installation_when_image_bytes_differ(tmp_path, monkeypatch):
    import subprocess
    (tmp_path / 'release.json').write_text(json.dumps({'files': {'backend/app/main.py': 'expected'}}))
    calls = []
    monkeypatch.setattr(d.r, 'run', lambda *args, **kwargs: calls.append(args) or 'sha256:image')
    def mismatch(args, **kwargs):
        assert '-i' in args and '-c' in args
        assert json.loads(kwargs['input']) == {'app/main.py': 'expected'}
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(d.subprocess, 'run', mismatch)
    with pytest.raises(subprocess.CalledProcessError):
        d.build(tmp_path, tmp_path, 'test-image')
    assert '--no-cache' in calls[0]
    assert not (tmp_path / 'INSTALL_TEST_IMAGE_ID').exists()
    assert not (tmp_path / 'installation-tests.log').exists()
