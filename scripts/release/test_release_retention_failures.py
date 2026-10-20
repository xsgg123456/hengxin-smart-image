"""Real ledger + managed publication + Docker command-contract integration."""
import pytest

from test_release_retention import fleet, image, invoke, ledger, retention, state
from test_release_retention_docker import Runner, module


@pytest.fixture
def setup(tmp_path):
    store = state.Store(tmp_path)
    store.write(ledger())
    runner = Runner()
    runner.images[image(3)]['RepoTags'] = [module.REPO + 'overseas-failed']
    runner.images[image(4)]['RepoTags'] = [module.REPO + 'overseas-new']
    return store, runner, module.Docker(runner)


def fail_build(setup, release='overseas-failed', action='build'):
    store, runner, docker = setup
    def fail():
        raise RuntimeError('build or prepare failed')
    with pytest.raises(RuntimeError, match='build or prepare'):
        invoke(fail, release, action, store, docker)


def publish(setup, group='overseas', release='overseas-new', number=4):
    store, runner, docker = setup
    def deploy():
        for service in module.TOPOLOGY[group][1]:
            runner.containers[group + '-' + service]['Image'] = image(number)
        return 'verified'
    return invoke(deploy, release, 'deploy', store, docker)


def mutations(runner):
    return [c for c in runner.calls if c[:3] in
            [('docker', 'image', 'rm'), ('docker', 'buildx', 'prune')]]


@pytest.mark.parametrize('action', ['build', 'prepare'])
def test_failed_candidate_retires_after_same_business_verified_success(setup, action):
    store, runner, docker = setup
    fail_build(setup, action=action)
    assert store.load()['pending']['overseas-failed']['failedAtSuccess'] == {'overseas': 0}
    assert mutations(runner) == []
    assert publish(setup) == 'verified'
    data = store.load()
    assert data['pending'] == {}
    assert data['retiredFailures']['overseas-failed']['pending']['image'] == image(3)
    assert data['retiredFailures']['overseas-failed']['successCounters'] == {'overseas': 1}
    assert data['groups']['domestic'] == ledger()['groups']['domestic']
    assert data['groups']['overseas'] == {'current': fleet(4)['overseas'], 'previous': fleet(2)['overseas']}
    assert ('docker', 'image', 'rm', module.REPO + 'overseas-failed') in mutations(runner)
    assert mutations(runner)[-1] == ('docker', 'buildx', 'prune', '--builder', 'hengxin-release',
                                    '--max-used-space', '2gb', '--force')
    saved = store.path.read_bytes()
    invoke(lambda: pytest.fail('must not replay'), 'overseas-new', 'deploy', store, docker)
    assert store.path.read_bytes() == saved


def test_other_business_success_cannot_retire_or_prune_failed_candidate(setup):
    store, runner, _ = setup
    fail_build(setup)
    publish(setup, group='domestic')
    assert store.load()['successCounters'] == {'domestic': 1}
    assert 'overseas-failed' in store.load()['pending']
    assert ('docker', 'image', 'rm', module.REPO + 'overseas-failed') not in mutations(runner)
    assert not any(c[:3] == ('docker', 'buildx', 'prune') for c in mutations(runner))


def test_old_success_and_failed_retry_do_not_count_as_replacement(setup):
    store, runner, docker = setup
    publish(setup)
    fail_build(setup)
    assert store.load()['pending']['overseas-failed']['failedAtSuccess'] == {'overseas': 1}
    runner.calls.clear()
    retention.safe_cleanup(docker, store.load(), store)
    assert 'overseas-failed' in store.load()['pending']
    assert not any(c[:3] == ('docker', 'buildx', 'prune') for c in mutations(runner))


def test_legacy_failure_is_seeded_then_requires_a_new_verified_success(setup):
    store, runner, docker = setup
    data = ledger()
    data['successCounters'] = {'overseas': 5}
    data['pending']['overseas-failed'] = {'phase': 'failed', 'image': image(3)}
    store.write(data)
    retention.safe_cleanup(docker, data, store)
    assert store.load()['pending']['overseas-failed']['failedAtSuccess'] == {'overseas': 5}
    assert 'retiredFailures' not in store.load()
    publish(setup)
    assert store.load()['pending'] == {}
    assert store.load()['successCounters']['overseas'] == 6


@pytest.mark.parametrize('protected', ['before', 'receipt', 'stopped', 'current', 'previous',
                                      'other_pending', 'unknown_scope', 'built', 'prepared'])
def test_ambiguous_recovery_and_referenced_failures_stay_protected(setup, protected):
    store, runner, docker = setup
    fail_build(setup)
    data = store.load()
    pending = data['pending']['overseas-failed']
    data['successCounters'] = {'overseas': 1}
    if protected == 'before':
        pending['before'] = fleet(2)
    elif protected == 'receipt':
        retention.receipt_path(store, 'overseas-failed').write_text('{}')
    elif protected == 'stopped':
        runner.containers['stopped'] = {'Image': image(3), 'Config': {'Labels': {}},
                                        'State': {'Running': False}}
    elif protected in ('current', 'previous'):
        pending['image'] = image(2 if protected == 'current' else 1)
    elif protected == 'other_pending':
        data['pending']['other'] = {'phase': 'built', 'image': image(3)}
    elif protected == 'unknown_scope':
        data['pending']['unknown'] = data['pending'].pop('overseas-failed')
    else:
        pending['phase'] = protected
    store.write(data)
    before = store.path.read_bytes()
    retention.f.retire(data, store, docker)
    assert store.path.read_bytes() == before


def test_preview_is_read_only_and_reports_only_proven_retirements(setup):
    store, runner, docker = setup
    fail_build(setup)
    data = store.load()
    data['successCounters'] = {'overseas': 1}
    store.write(data)
    original = store.path.read_bytes()
    assert retention.f.preview(data, store, docker) == ['overseas-failed']
    assert store.path.read_bytes() == original and mutations(runner) == []


@pytest.mark.parametrize('release', ['domestic', 'overseas', 'identity', 'domestic-',
                                    'overseas-', 'identity-', 'unknown-version'])
def test_incomplete_or_unknown_release_names_never_retire(setup, release):
    store, runner, docker = setup
    group = release.partition('-')[0]
    data = ledger()
    data['successCounters'] = {g: 1 for g in retention.f.GROUPS}
    pending = {'phase': 'failed', 'image': image(3)}
    assert retention.f.scope(release, pending) is None
    data['pending'][release] = pending
    assert not retention.f.seed_legacy(data)
    pending['failedAtSuccess'] = {group if group in retention.f.GROUPS else 'overseas': 0}
    store.write(data)
    original = store.path.read_bytes()
    assert retention.f.preview(data, store, docker) == []
    retention.f.retire(data, store, docker)
    assert store.path.read_bytes() == original and mutations(runner) == []


def test_retirement_storage_failure_keeps_pending_and_stops_all_cleanup(setup, monkeypatch, capsys):
    store, runner, docker = setup
    fail_build(setup)
    data = store.load()
    data['successCounters'] = {'overseas': 1}
    store.write(data)
    def fail_write(_):
        raise OSError('disk failure')
    monkeypatch.setattr(store, 'write', fail_write)
    retention.safe_cleanup(docker, data, store)
    assert 'overseas-failed' in store.load()['pending'] and 'overseas-failed' in data['pending']
    assert mutations(runner) == [] and 'OSError' in capsys.readouterr().err


def test_new_container_reference_between_preview_and_retirement_is_protected(setup, monkeypatch):
    store, runner, docker = setup
    fail_build(setup)
    data = store.load()
    data['successCounters'] = {'overseas': 1}
    store.write(data)
    original = retention.f.preview
    calls = 0
    def race(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            runner.containers['stopped'] = {'Image': image(3), 'Config': {'Labels': {}},
                                            'State': {'Running': False}}
        return original(*args)
    monkeypatch.setattr(retention.f, 'preview', race)
    retention.f.retire(data, store, docker)
    assert 'overseas-failed' in store.load()['pending']


@pytest.mark.parametrize('bad', [-1, True, '1'])
def test_invalid_epoch_cannot_authorize_cleanup(bad):
    data = ledger()
    data['successCounters'] = {'overseas': bad}
    with pytest.raises(RuntimeError, match='counters'):
        state.validate(data)


def test_same_tag_rebuild_keeps_both_candidates_until_verified_replacement(setup):
    store, runner, docker = setup
    def failed_rebuild():
        runner.images[image(3)]['RepoTags'] = []
        runner.images[image(3)]['Config'] = {'Labels': {'io.hengxin.project': 'smart-image'}}
        runner.images[image(5)]['RepoTags'] = [module.REPO + 'overseas-failed']
        raise RuntimeError('rebuild failure')
    with pytest.raises(RuntimeError):
        invoke(failed_rebuild, 'overseas-failed', 'build', store, docker)
    assert {image(3), image(5)} <= set(docker.plan(store.load())['protected'])
    publish(setup)
    assert ('docker', 'image', 'rm', image(3)) in mutations(runner)
    assert ('docker', 'image', 'rm', module.REPO + 'overseas-failed') in mutations(runner)


def test_completed_release_cannot_be_rebuilt_and_rollback_stays_intact(setup):
    store, _, docker = setup
    publish(setup)
    saved = store.path.read_bytes()
    for action in ('build', 'prepare'):
        with pytest.raises(RuntimeError, match='completed'):
            invoke(lambda: pytest.fail('completed tag must not be rebuilt'), 'overseas-new', action, store, docker)
    assert store.path.read_bytes() == saved


@pytest.mark.parametrize('fault', ['unhealthy', 'drift', 'missing_rollback'])
def test_retirement_requires_healthy_unchanged_fleet_and_complete_rollback(setup, fault):
    store, runner, docker = setup
    fail_build(setup)
    data = store.load()
    data['successCounters'] = {'overseas': 1}
    store.write(data)
    if fault == 'unhealthy':
        runner.containers['overseas-api']['State']['Health']['Status'] = 'unhealthy'
    elif fault == 'drift':
        runner.containers['overseas-api']['Image'] = image(8)
    else:
        del runner.images[image(1)]
    with pytest.raises((RuntimeError, StopIteration)):
        retention.f.retire(data, store, docker)
    assert 'overseas-failed' in store.load()['pending'] and mutations(runner) == []


def test_later_retry_failure_resets_epoch_instead_of_using_old_success(setup):
    store, runner, docker = setup
    fail_build(setup)
    runner.containers['stopped'] = {'Image': image(3), 'Config': {'Labels': {}},
                                    'State': {'Running': False}}
    publish(setup)
    assert 'overseas-failed' in store.load()['pending']
    del runner.containers['stopped']
    fail_build(setup)
    assert store.load()['pending']['overseas-failed']['failedAtSuccess'] == {'overseas': 1}
    assert retention.f.preview(store.load(), store, docker) == []
