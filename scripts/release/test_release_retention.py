"""Release transaction regressions; temporary real ledger, no Docker daemon."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


retention = load('release-retention')
state = retention.s


def image(number):
    return 'sha256:' + format(number, '064x')


def fleet(number):
    return {group: {service: image(number) for service in services}
            for group, (_, services) in retention.d.TOPOLOGY.items()}


def ledger(current=2, previous=1):
    live, old = fleet(current), fleet(previous)
    return {'version': 1, 'groups': {
        group: {'current': live[group], 'previous': old[group]} for group in state.GROUPS
    }, 'pending': {}}


class FakeDocker:
    def __init__(self, live):
        self.live = live
        self.cleaned = []
        self.tags = {'A': image(3), 'B': image(4), 'C': image(5)}
        self.cleanup_error = None

    def snapshot(self):
        return deepcopy(self.live)

    def candidate(self, release):
        return self.tags.get(release)

    def cleanup(self, data, store):
        self.cleaned.append(deepcopy(data))
        if self.cleanup_error:
            raise self.cleanup_error


@pytest.fixture
def setup(tmp_path):
    store = state.Store(tmp_path / 'state')
    store.write(ledger())
    return store, FakeDocker(fleet(2))


def invoke(main, release, action, store, docker):
    return retention.managed(main, ['release.py', release, action], store, docker)


def test_three_successes_advance_each_group_and_repeat_is_idempotent(setup):
    store, docker = setup
    for number, release in [(3, 'A'), (4, 'B'), (5, 'C')]:
        def deploy():
            docker.live = fleet(number)
            return 'verified'
        assert invoke(deploy, release, 'deploy', store, docker) == 'verified'
        for group, history in store.load()['groups'].items():
            assert history == {'current': fleet(number)[group], 'previous': fleet(number - 1)[group]}
        saved = store.path.read_bytes()
        invoke(lambda: pytest.fail('completed deployment must not execute twice'),
               release, 'deploy', store, docker)
        assert store.path.read_bytes() == saved
    assert store.load()['pending'] == {}


def test_unchanged_groups_preserve_their_previous_success(setup):
    store, docker = setup
    def deploy():
        docker.live['overseas'] = fleet(3)['overseas']
    invoke(deploy, 'A', 'deploy', store, docker)
    data = store.load()
    for group in ('domestic', 'identity'):
        assert data['groups'][group] == ledger()['groups'][group]
    assert data['groups']['overseas'] == {'current': fleet(3)['overseas'], 'previous': fleet(2)['overseas']}


@pytest.mark.parametrize('action', ['recover', 'resume'])
def test_failed_partial_deploy_keeps_history_and_recovery_uses_saved_before(setup, action):
    store, docker = setup
    def fail():
        docker.live['overseas'] = fleet(3)['overseas']
        raise RuntimeError('verification failed')
    with pytest.raises(RuntimeError, match='verification failed'):
        invoke(fail, 'A', 'deploy', store, docker)
    data = store.load()
    assert data['groups'] == ledger()['groups']
    assert data['pending']['A']['before'] == fleet(2)
    assert data['pending']['A']['phase'] == 'failed'
    assert docker.cleaned == []
    def recover():
        docker.live = fleet(3)
    invoke(recover, 'A', action, store, docker)
    assert store.load()['pending'] == {}
    for group, history in store.load()['groups'].items():
        assert history['previous'] == fleet(2)[group]
        assert history['current'] == fleet(3)[group]


@pytest.mark.parametrize('action,phase', [('build', 'built'), ('prepare', 'prepared')])
def test_build_and_prepare_retain_candidates_without_advancing(setup, action, phase):
    store, docker = setup
    def build():
        docker.tags['A'] = image(3)
    invoke(build, 'A', action, store, docker)
    data = store.load()
    assert data['groups'] == ledger()['groups']
    assert data['pending']['A'] == {'phase': phase, 'image': image(3)}
    assert docker.cleaned == []


def test_cleanup_failure_does_not_turn_verified_main_into_failure(setup, capsys):
    store, docker = setup
    docker.cleanup_error = RuntimeError('disk or docker failure')
    def deploy():
        docker.live = fleet(3)
        return 42
    assert invoke(deploy, 'A', 'deploy', store, docker) == 42
    assert 'A' in store.load()['completed']
    assert store.load()['pending'] == {}
    assert 'RuntimeError' in capsys.readouterr().err


def test_post_verification_snapshot_failure_forbids_cleanup(setup):
    store, docker = setup
    def deploy():
        def broken():
            raise RuntimeError('inspection failed')
        docker.snapshot = broken
        return 42
    assert invoke(deploy, 'A', 'deploy', store, docker) == 42
    assert docker.cleaned == []
    assert store.load()['groups'] == ledger()['groups']
    assert store.load()['pending']['A']['before'] == fleet(2)


def test_drift_refuses_main_and_cleanup(setup):
    store, docker = setup
    docker.live = fleet(8)
    with pytest.raises(RuntimeError, match='drift'):
        invoke(lambda: pytest.fail('must not deploy'), 'A', 'deploy', store, docker)
    assert docker.cleaned == []


@pytest.mark.parametrize('content', ['{', '{}', '{"version":2,"groups":{},"pending":{}}'])
def test_corrupt_ledger_refuses_main_and_cleanup(setup, content):
    store, docker = setup
    store.path.write_text(content, encoding='utf-8')
    with pytest.raises((RuntimeError, json.JSONDecodeError)):
        invoke(lambda: pytest.fail('must not deploy'), 'A', 'deploy', store, docker)
    assert docker.cleaned == []


def test_host_lock_excludes_second_store_and_releases_after_exception(tmp_path):
    one, two = state.Store(tmp_path), state.Store(tmp_path)
    with pytest.raises(ValueError):
        with one.locked():
            with pytest.raises(OSError):
                with two.locked():
                    pytest.fail('concurrent writer acquired lock')
            raise ValueError('deployment failed')
    with two.locked():
        two.write(ledger())
    assert one.load() == ledger()


@pytest.mark.parametrize('action', ['recover', 'resume'])
def test_recovery_requires_saved_snapshot(setup, action):
    store, docker = setup
    with pytest.raises(RuntimeError, match='saved'):
        invoke(lambda: pytest.fail('must not run recovery'), 'A', action, store, docker)


def test_verified_deploy_snapshot_failure_retries_without_replaying_main(setup):
    store, docker = setup
    snapshot = docker.snapshot
    def deploy():
        docker.live = fleet(3)
        def unavailable():
            raise RuntimeError('Docker inspection unavailable')
        docker.snapshot = unavailable
    invoke(deploy, 'A', 'deploy', store, docker)
    assert retention.receipt_path(store, 'A').exists()
    assert docker.cleaned == []
    docker.snapshot = snapshot
    invoke(lambda: pytest.fail('must not replay successful deploy'), 'A', 'deploy', store, docker)
    assert store.load()['groups']['overseas']['previous'] == fleet(2)['overseas']
    assert store.load()['groups']['overseas']['current'] == fleet(3)['overseas']


def test_verified_ledger_write_failure_can_finalize_but_rejects_unrelated_drift(setup):
    store, docker = setup
    write = store.write
    def fail_completion(data):
        if 'A' in data.get('completed', {}):
            raise OSError('disk temporarily unavailable')
        write(data)
    store.write = fail_completion
    invoke(lambda: setattr(docker, 'live', fleet(3)), 'A', 'deploy', store, docker)
    assert store.load()['pending']['A']['before'] == fleet(2)
    assert docker.cleaned == []
    store.write = write
    docker.live = fleet(9)
    with pytest.raises(RuntimeError, match='drift'):
        invoke(lambda: pytest.fail('must not run recovery'), 'A', 'recover', store, docker)
    docker.live = fleet(3)
    invoke(lambda: pytest.fail('must not run recovery'), 'A', 'recover', store, docker)
    assert 'A' in store.load()['completed']
