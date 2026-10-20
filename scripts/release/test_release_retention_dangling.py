"""Scoped dangling-image discovery and non-forced cleanup race regressions."""
import json
import subprocess

import pytest

from test_release_retention import fleet, image, ledger, state
from test_release_retention_docker import Runner, module


LABEL = {'io.hengxin.project': 'smart-image'}


def dangling(runner, number):
    runner.add_image(number, tags=[], labels=LABEL)


def test_discovery_merges_filtered_tagged_and_project_dangling_queries():
    runner = Runner()
    dangling(runner, 10)
    runner.add_image(11, tags=[])
    runner.add_image(12, tags=[], labels={'io.hengxin.project': 'other'})
    runner.add_image(13, tags=['another-project:only'], labels=LABEL)
    runner.add_image(14, tags=[], digests=[module.REPO[:-1] + '@sha256:' + 'a' * 64], labels=LABEL)
    assert {item['Id'] for item in module.Docker(runner).images()} == {
        image(number) for number in range(1, 11)}
    queries = [call for call in runner.calls if call[:3] == ('docker', 'image', 'ls')]
    assert len(queries) == 2
    assert set(runner(*queries[0], capture=True).split()) == {image(n) for n in range(1, 10)}
    assert runner(*queries[1], capture=True).split() == [image(10)]
    inspections = [call for call in runner.calls if call[:3] == ('docker', 'image', 'inspect')]
    assert len(inspections) == 1 and len(inspections[0][3:]) == 10


def test_dangling_protects_history_pending_before_and_stopped_containers():
    runner, data = Runner(), ledger()
    for number in [1, 2, 3, 5, 6, 7]:
        dangling(runner, number)
    runner.images[image(4)]['RepoTags'] = [module.REPO + 'pending']
    data['pending']['pending'] = {'phase': 'prepared', 'image': image(3), 'before': fleet(5)}
    runner.containers['stopped'] = {
        'Image': image(6), 'Config': {'Labels': {}}, 'State': {'Running': False}}
    plan = module.Docker(runner).plan(data)
    assert set(plan['protected']) == {image(number) for number in range(1, 7)}
    assert {'id': image(7), 'tags': []} in plan['remove']
    assert {item['id'] for item in plan['remove']} == {image(7), image(8), image(9)}


def test_dangling_retains_each_groups_distinct_current_and_previous():
    runner, data = Runner(), ledger()
    for index, (group, (_, services)) in enumerate(module.TOPOLOGY.items()):
        current, previous = index * 2 + 1, index * 2 + 2
        dangling(runner, current)
        dangling(runner, previous)
        data['groups'][group] = {
            'current': fleet(current)[group], 'previous': fleet(previous)[group]}
        for service in services:
            runner.containers[group + '-' + service]['Image'] = image(current)
    plan = module.Docker(runner).plan(data)
    assert set(plan['protected']) == {image(number) for number in range(1, 7)}
    assert {item['id'] for item in plan['remove']} == {image(7), image(8), image(9)}


@pytest.mark.parametrize('metadata', [
    {'Config': {'Labels': {}}},
    {'Config': {'Labels': {'io.hengxin.project': 'other'}}},
    {'Config': None},
    {'RepoTags': ['other-project:claimed']},
    {'RepoDigests': [module.REPO[:-1] + '@sha256:' + 'a' * 64]},
    {'RepoDigests': ['other-project@sha256:' + 'b' * 64]},
])
def test_inspected_metadata_rejects_changed_scope_or_digest_only_image(metadata):
    runner = Runner()
    dangling(runner, 10)
    original = runner.__call__

    def race(*args, **kwargs):
        if args[:3] == ('docker', 'image', 'inspect') and image(10) in args[3:]:
            runner.images[image(10)].update(metadata)
        return original(*args, **kwargs)

    assert image(10) not in {item['id'] for item in module.Docker(race).plan(ledger())['remove']}


def test_cleanup_removes_dangling_by_full_id_and_tagged_by_tag(tmp_path):
    runner = Runner()
    dangling(runner, 10)
    removed = module.Docker(runner).cleanup(ledger(), state.Store(tmp_path))
    assert {'id': image(10), 'tags': []} in removed
    commands = [call for call in runner.calls if call[:3] == ('docker', 'image', 'rm')]
    assert ('docker', 'image', 'rm', image(10)) in commands
    assert ('docker', 'image', 'rm', module.REPO + '3') in commands
    assert all('-f' not in call and '--force' not in call for call in commands)
    assert json.loads((tmp_path / 'cleanup-result.json').read_text())['removed'] == removed


@pytest.mark.parametrize('new_reference', ['container', 'project_tag', 'external_tag', 'digest', 'pending'])
def test_cleanup_rechecks_dangling_references_and_aliases_before_removal(tmp_path, new_reference):
    runner, data = Runner(), ledger()
    dangling(runner, 3)
    docker = module.Docker(runner)
    original = docker.plan
    count = 0

    def race(data):
        nonlocal count
        count += 1
        if count == 2:
            if new_reference == 'container':
                runner.containers['new-stopped'] = {
                    'Image': image(3), 'Config': {'Labels': {}}, 'State': {'Running': False}}
            elif new_reference == 'project_tag':
                runner.images[image(3)]['RepoTags'] = [module.REPO + 'new']
            elif new_reference == 'external_tag':
                runner.images[image(3)]['RepoTags'] = ['another-project:new']
            elif new_reference == 'digest':
                runner.images[image(3)]['RepoDigests'] = [module.REPO[:-1] + '@sha256:' + 'a' * 64]
            else:
                data['pending']['new'] = {'phase': 'prepared', 'image': image(3)}
        return original(data)

    docker.plan = race
    removed = docker.cleanup(data, state.Store(tmp_path))
    assert image(3) not in {item['id'] for item in removed}
    assert ('docker', 'image', 'rm', image(3)) not in runner.calls


def test_failed_dangling_removal_stops_cleanup_and_cache_pruning(tmp_path):
    runner = Runner()
    dangling(runner, 3)
    original = runner.__call__

    def reject(*args, **kwargs):
        if args == ('docker', 'image', 'rm', image(3)):
            runner.calls.append(args)
            raise subprocess.CalledProcessError(1, args, stderr='image is in use')
        return original(*args, **kwargs)

    with pytest.raises(subprocess.CalledProcessError):
        module.Docker(reject).cleanup(ledger(), state.Store(tmp_path))
    commands = [call for call in runner.calls if call[:3] == ('docker', 'image', 'rm')]
    assert commands == [('docker', 'image', 'rm', image(3))]
    assert not any(call[:3] == ('docker', 'buildx', 'prune') for call in runner.calls)
    assert not (tmp_path / 'cleanup-result.json').exists()
