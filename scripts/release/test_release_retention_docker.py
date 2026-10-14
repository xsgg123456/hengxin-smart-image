"""Docker command contracts using metadata fixtures, never a real daemon."""
from copy import deepcopy
import json

import pytest

from test_release_retention import fleet, image, ledger, load, state


module = load('release-retention-docker')
build = load('release-build')


class Runner:
    def __init__(self):
        self.calls = []
        self.images = {}
        self.containers = {}
        self.builders = [{'Name': build.BUILDER, 'Driver': 'docker-container'}]
        for group, (project, services) in module.TOPOLOGY.items():
            for service in services:
                name = group + '-' + service
                self.containers[name] = {
                    'Id': name, 'Image': image(2),
                    'Config': {'Labels': {'com.docker.compose.project': project,
                                          'com.docker.compose.service': service}},
                    'State': {'Running': True, 'Health': {'Status': 'healthy'}},
                }
        for number in range(1, 10):
            self.add_image(number)

    def add_image(self, number, tags=None, digests=None):
        self.images[image(number)] = {
            'Id': image(number), 'RepoTags': tags or [module.REPO + str(number)],
            'RepoDigests': digests or [],
        }

    def __call__(self, *args, capture=False):
        self.calls.append(args)
        if args == ('docker', 'ps', '-aq'):
            return '\n'.join(self.containers)
        if args[:3] == ('docker', 'container', 'inspect'):
            return json.dumps([self.containers[name] for name in args[3:]])
        if args[:3] == ('docker', 'image', 'ls'):
            assert args[3:] == ('--filter', 'reference=' + module.REPO + '*', '--no-trunc', '--quiet')
            return '\n'.join(self.images)
        if args[:3] == ('docker', 'image', 'inspect'):
            return json.dumps([next(value for key, value in self.images.items()
                                    if ref == key or ref in value['RepoTags']) for ref in args[3:]])
        if args == ('docker', 'buildx', 'ls', '--format', '{{json .Builder}}'):
            return '\n'.join(json.dumps(value) for value in self.builders)
        if args[:3] == ('docker', 'buildx', 'create'):
            self.builders.append({'Name': build.BUILDER, 'Driver': 'docker-container'})
            return None
        if args[:3] in [('docker', 'image', 'rm'), ('docker', 'buildx', 'prune'),
                        ('docker', 'buildx', 'build')]:
            return None
        raise AssertionError('Unexpected Docker command: ' + repr(args))


def test_plan_protects_current_previous_pending_and_stopped_containers():
    runner, data = Runner(), ledger()
    runner.images[image(4)]['RepoTags'] = [module.REPO + 'pending']
    data['pending']['pending'] = {'phase': 'failed', 'image': image(3), 'before': fleet(5)}
    runner.containers['unrelated-stopped'] = {
        'Id': 'unrelated-stopped', 'Image': image(6), 'Config': {'Labels': {}},
        'State': {'Running': False},
    }
    plan = module.Docker(runner).plan(data)
    assert set(plan['protected']) == {image(number) for number in range(1, 7)}
    assert {item['id'] for item in plan['remove']} == {image(7), image(8), image(9)}
    assert ('docker', 'ps', '-aq') in runner.calls


def test_plan_excludes_external_tag_or_digest_aliases():
    runner = Runner()
    runner.images[image(3)]['RepoTags'].append('another-project:shared')
    runner.images[image(4)]['RepoDigests'] = ['registry.example.com/other@sha256:' + 'a' * 64]
    runner.images[image(5)]['RepoDigests'] = [module.REPO[:-1] + '@sha256:' + 'b' * 64]
    plan = module.Docker(runner).plan(ledger())
    removed = {item['id'] for item in plan['remove']}
    assert image(3) not in removed
    assert image(4) not in removed
    assert image(5) in removed


@pytest.mark.parametrize('invalid', ['no_previous', 'missing_group', 'drift'])
def test_cleanup_refuses_incomplete_or_drifted_history(tmp_path, invalid):
    runner, data = Runner(), ledger()
    if invalid == 'no_previous':
        data['groups']['identity']['previous'] = None
    elif invalid == 'missing_group':
        del data['groups']['identity']
    else:
        data['groups']['identity']['current'] = fleet(9)['identity']
    with pytest.raises(RuntimeError):
        module.Docker(runner).cleanup(data, state.Store(tmp_path))
    assert not any(call[:3] in [('docker', 'image', 'rm'), ('docker', 'buildx', 'prune')]
                   for call in runner.calls)


def test_cleanup_only_removes_explicit_tags_without_force_and_prunes_project_builder(tmp_path):
    runner = Runner()
    store = state.Store(tmp_path)
    removed = module.Docker(runner).cleanup(ledger(), store)
    assert len(removed) == 7
    mutations = [call for call in runner.calls if call[:3] in
                 [('docker', 'image', 'rm'), ('docker', 'buildx', 'prune')]]
    assert mutations[-1] == ('docker', 'buildx', 'prune', '--builder', build.BUILDER,
                              '--max-used-space', '2gb', '--force')
    for command in mutations[:-1]:
        assert command[:3] == ('docker', 'image', 'rm')
        assert all(tag.startswith(module.REPO) for tag in command[3:])
        assert '-f' not in command and '--force' not in command
    assert json.loads((tmp_path / 'cleanup-result.json').read_text())['removed'] == removed
    assert (tmp_path / 'cleanup-plan.json').exists()


def test_pending_release_prevents_cache_pruning(tmp_path):
    runner, data = Runner(), ledger()
    data['pending']['A'] = {'phase': 'prepared', 'image': image(3)}
    module.Docker(runner).cleanup(data, state.Store(tmp_path))
    assert not any(call[:3] == ('docker', 'buildx', 'prune') for call in runner.calls)


def test_rechecks_new_references_before_removal(tmp_path):
    runner, docker = Runner(), None
    docker = module.Docker(runner)
    original = docker.plan
    count = 0
    def race(data):
        nonlocal count
        count += 1
        if count == 2:
            runner.containers['new-stopped'] = {'Image': image(3), 'Config': {'Labels': {}},
                                                 'State': {'Running': False}}
        return original(data)
    docker.plan = race
    docker.cleanup(ledger(), state.Store(tmp_path))
    assert ('docker', 'image', 'rm', module.REPO + '3') not in runner.calls


@pytest.mark.parametrize('fault', ['unhealthy', 'missing', 'duplicate'])
def test_fleet_snapshot_rejects_unhealthy_missing_or_duplicate_services(fault):
    runner = Runner()
    name = 'overseas-api'
    if fault == 'unhealthy':
        runner.containers[name]['State']['Health']['Status'] = 'unhealthy'
    elif fault == 'missing':
        runner.containers[name]['State']['Running'] = False
    else:
        runner.containers['duplicate'] = deepcopy(runner.containers[name])
    with pytest.raises(RuntimeError):
        module.Docker(runner).snapshot()


def test_candidate_matches_exact_release_tag_and_resolve_requires_project_image():
    runner = Runner()
    runner.images[image(3)]['RepoTags'] = [module.REPO + 'release-A']
    runner.images[image(4)]['RepoTags'] = ['another-project:release-A']
    docker = module.Docker(runner)
    assert docker.candidate('release-A') == image(3)
    assert docker.candidate('release') is None
    assert docker.resolve(module.REPO + 'release-A') == image(3)
    with pytest.raises(RuntimeError):
        docker.resolve('another-project:release-A')


def test_build_creates_isolated_builder_and_uses_load_and_no_cache(monkeypatch):
    runner = Runner()
    runner.builders = [{'Name': 'default', 'Driver': 'docker'}]
    monkeypatch.setenv('HENGXIN_RELEASE_NO_CACHE', '1')
    build.build('source', module.REPO + 'release-A', runner)
    assert ('docker', 'buildx', 'create', '--name', build.BUILDER,
            '--driver', 'docker-container') in runner.calls
    command = runner.calls[-1]
    assert command[:5] == ('docker', 'buildx', 'build', '--builder', build.BUILDER)
    assert '--load' in command and '--no-cache' in command
    assert command[command.index('-t') + 1] == module.REPO + 'release-A'


def test_builder_wrong_driver_forbids_build_and_prune(tmp_path):
    runner = Runner()
    runner.builders = [{'Name': build.BUILDER, 'Driver': 'docker'}]
    with pytest.raises(RuntimeError):
        build.build('source', module.REPO + 'A', runner)
    with pytest.raises(RuntimeError):
        module.Docker(runner).cleanup(ledger(), state.Store(tmp_path))
    assert not any(call[:3] in [('docker', 'buildx', 'build'), ('docker', 'buildx', 'prune')]
                   for call in runner.calls)
