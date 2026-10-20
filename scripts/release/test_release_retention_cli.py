"""CLI initialization and manual recovery controls against a fake Docker daemon."""
import pytest

from test_release_retention import image, ledger, retention, state
from test_release_retention_docker import Runner, module


@pytest.fixture
def cli(tmp_path, monkeypatch):
    store, runner = state.Store(tmp_path), Runner()
    monkeypatch.setattr(retention.s, 'Store', lambda: store)
    monkeypatch.setattr(retention.d, 'Docker', lambda: module.Docker(runner))
    def invoke(*args):
        monkeypatch.setattr(retention.sys, 'argv', ['release-retention.py', *args])
        retention.main()
    return store, runner, invoke


def init_args():
    return ['init', '--domestic-previous', image(1), '--overseas-previous', image(1),
            '--identity-previous', image(1)]


def test_init_and_preview_do_not_mutate_docker_and_cannot_reset_history(cli, capsys):
    store, runner, invoke = cli
    invoke(*init_args())
    assert store.load() == ledger()
    invoke('preview')
    assert 'protected' in capsys.readouterr().out
    invoke('init', '--domestic-previous', image(9))
    assert store.load() == ledger()
    assert not any(call[:3] in [('docker', 'image', 'rm'), ('docker', 'buildx', 'prune')]
                   for call in runner.calls)


def test_init_can_fill_missing_history_while_preserving_built_candidate(cli):
    store, _, invoke = cli
    data = ledger()
    data['groups']['identity']['previous'] = None
    data['pending']['A'] = {'phase': 'built', 'image': image(3)}
    store.write(data)
    invoke('init', '--identity-previous', image(1))
    assert store.load()['groups'] == ledger()['groups']
    assert store.load()['pending'] == data['pending']


def test_abandon_only_unpins_candidate_without_deleting_anything(cli):
    store, runner, invoke = cli
    data = ledger()
    data['pending']['A'] = {'phase': 'built', 'image': image(3)}
    store.write(data)
    invoke('abandon', '--release', 'A')
    assert store.load()['pending'] == {}
    assert not any(call[:3] in [('docker', 'image', 'rm'), ('docker', 'buildx', 'prune')]
                   for call in runner.calls)


def test_missing_retained_image_forbids_cleanup(cli):
    store, runner, invoke = cli
    store.write(ledger())
    del runner.images[image(1)]
    with pytest.raises((RuntimeError, StopIteration)):
        invoke('cleanup')
    assert not any(call[:3] == ('docker', 'image', 'rm') for call in runner.calls)


def test_cli_preview_then_cleanup_retires_proven_failure_without_touching_services(cli, capsys):
    store, runner, invoke = cli
    data = ledger()
    data['successCounters'] = {'overseas': 1}
    data['pending']['overseas-old'] = {'phase': 'failed', 'image': image(3),
                                      'failedAtSuccess': {'overseas': 0}}
    store.write(data)
    before = store.path.read_bytes()
    invoke('preview')
    assert 'overseas-old' in capsys.readouterr().out and store.path.read_bytes() == before
    invoke('cleanup')
    after = store.load()
    assert after['groups'] == data['groups'] and after['pending'] == {}
    assert 'overseas-old' in after['retiredFailures']
    assert ('docker', 'image', 'rm', module.REPO + '3') in runner.calls
    assert not any(c[0] in ('systemctl', 'rm') or c[:2] in
                   [('docker', 'stop'), ('docker', 'volume'), ('docker', 'system')]
                   for c in runner.calls)
