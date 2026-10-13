"""Reload settling and strict pre-migration recovery boundaries."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


r = module('member-release-resume')
v = module('member-release-verify')


def test_closed_waits_for_all_four_paths_after_reload(monkeypatch):
    replies = iter(['401', '503', '503', '503'] + ['503'] * 4)
    calls, sleeps = [], []
    monkeypatch.setattr(v, 'status', lambda url: calls.append(url) or next(replies))
    monkeypatch.setattr(v.time, 'sleep', sleeps.append)
    v.closed()
    assert len(calls) == 8 and calls[:4] == calls[4:] and sleeps == [1]


def test_closed_never_succeeds_on_timeout(monkeypatch):
    monkeypatch.setattr(v, 'status', lambda url: '401')
    with pytest.raises(AssertionError, match='Public intake is not closed'):
        v.closed(timeout=0)


def baseline(tmp_path):
    groups = {name: {'api': 'api'} for name in ('domestic', 'overseas', 'identity')}
    data = {'nativeFiles': {'/native.env': 'unchanged'}, 'native': {'worker': '/native'}}
    live, digests, running = {}, {'/native.env': 'unchanged'}, {}
    (tmp_path / 'deploy.exit').write_text('1')
    edge = tmp_path / 'edge.conf'
    edge.write_text('closed:original')
    for group in groups:
        api, worker = group + '-api', group + '-worker'
        ids = {api: group + '-api-id', worker: group + '-worker-id'}
        mounts = {name: [{'Destination': '/data', 'RW': True}] for name in ids}
        data[group] = dict(project=group, files={group + '.env': 'unchanged'}, ids=ids,
            mounts=copy.deepcopy(mounts), paths=['/compose'], cwd='/cwd', env=None)
        digests[group + '.env'] = 'unchanged'
        running[group] = ids[worker]
        (tmp_path / (group + '-compose.private.json')).write_text(json.dumps({'services': {'api': {'image': 'old'}}}))
        for name, identity in ids.items():
            live[name] = dict(Id=identity, Mounts=mounts[name], State=dict(Running=name != api, Status='exited', ExitCode=0, OOMKilled=False),
                Config={'Image': 'old', 'Labels': {'com.docker.compose.project': group,
                    'com.docker.compose.project.config_files': '/compose',
                    'com.docker.compose.project.working_dir': '/cwd'}})
    def run(*args, **kwargs):
        if args[:2] == ('docker', 'ps'):
            return running[args[-1].split('=')[-1]]
        if 'WorkingDirectory' in args: return '/native'
        return '/native.env' if 'show' in args else ''
    m = SimpleNamespace(GROUPS=groups, EDGE=edge, closed_config=lambda text: 'closed:' + text,
        container=lambda group, service: group + '-' + service, digest=digests.__getitem__,
        live=live.__getitem__, run=run, prepared_settings=lambda *args: None)
    return m, data, live, digests, running


def test_recovery_accepts_only_stopped_apis_and_original_running_resources(tmp_path):
    m, data, live, *_ = baseline(tmp_path)
    r.check_baseline(m, tmp_path, data, 'original')
    live['domestic-api']['State']['ExitCode'] = 143
    live['overseas-api']['State']['ExitCode'] = 143
    r.check_baseline(m, tmp_path, data, 'original')


@pytest.mark.parametrize('marker', ['MIGRATION_STARTED', 'EXECUTORS_STOPPED',
    'drained-before-outbox-stop.json', 'drained-after-outbox-stop.json', 'verification.json'])
def test_recovery_rejects_progressed_attempt(tmp_path, marker):
    m, data, *_ = baseline(tmp_path)
    (tmp_path / marker).write_text('started')
    with pytest.raises(AssertionError):
        r.check_baseline(m, tmp_path, data, 'original')


@pytest.mark.parametrize('change', ['running-api', 'container-id', 'mount', 'image', 'compose', 'native',
    'extra-running', 'missing-worker', 'edge', 'labels', 'crashed-api', 'oom', 'killed-api',
    'new-native-path', 'missing-native-path'])
def test_recovery_rejects_drift(tmp_path, change):
    m, data, live, digests, running = baseline(tmp_path)
    api = live['domestic-api']
    if change == 'running-api': api['State']['Running'] = True
    elif change == 'container-id': api['Id'] = 'replacement'
    elif change == 'mount': api['Mounts'][0]['RW'] = False
    elif change == 'image': api['Config']['Image'] = 'new'
    elif change == 'compose': digests['domestic.env'] = 'changed'
    elif change == 'native': digests['/native.env'] = 'changed'
    elif change == 'extra-running': running['domestic'] += ' extra'
    elif change == 'missing-worker': running['domestic'] = ''
    elif change == 'edge': m.EDGE.write_text('open')
    elif change == 'labels': api['Config']['Labels']['com.docker.compose.project.working_dir'] = '/other'
    elif change == 'crashed-api': api['State']['ExitCode'] = 1
    elif change == 'oom': api['State']['OOMKilled'] = True
    elif change == 'killed-api': api['State']['ExitCode'] = 137
    elif change in ('new-native-path', 'missing-native-path'):
        original_run = m.run
        def changed_run(*args, **kwargs):
            if 'show' in args and 'WorkingDirectory' not in args:
                return '/native.env /extra' if change == 'new-native-path' else ''
            return original_run(*args, **kwargs)
        m.run = changed_run
    with pytest.raises(AssertionError):
        r.check_baseline(m, tmp_path, data, 'original')
