import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import image_gc as gc


def image(n):
    return 'sha256:' + format(n, '064x')


class Docker:
    APPS = tuple('app-' + str(i) for i in range(9))
    DATA = {'data-' + str(i) for i in range(7)}

    def __init__(self):
        self.calls, self.rows, self.present = [], [], {image(1), image(2), image(3), image(4)}
        self.fail_remove = self.keep_remove = False
        self.on_scan = None
        self.scans = 0
        for i, service in enumerate(sorted(set(self.APPS) | self.DATA | {'https'})):
            self.rows.append({'Id': format(i, '064x'), 'Name': '/hengxin-lan-' + service,
                              'Image': image(1), 'State': {'Running': True},
                              'Config': {'Labels': {'com.docker.compose.service': service,
                                  'com.docker.compose.project':
                                      'hengxin-lan-edge' if service == 'https' else 'hengxin-lan'}}})

    def run(self, args):
        self.calls.append(args[:])
        if args == ['docker', 'ps', '-aq', '--no-trunc']:
            self.scans += 1
            if self.on_scan:
                self.on_scan(self.scans)
            return '\n'.join(row['Id'] for row in self.rows)
        if args[:2] == ['docker', 'inspect']:
            return json.dumps([row for row in self.rows if row['Id'] in args[2:]])
        if args == ['docker', 'image', 'ls', '-aq', '--no-trunc']:
            return '\n'.join(sorted(self.present))
        if args == gc.DF:
            return json.dumps({'LayersSize': len(self.present) * 100})
        if args[:4] == ['docker', 'image', 'rm', '--no-prune']:
            assert len(args) == 5 and args[4] in self.present
            if self.fail_remove:
                raise RuntimeError('sensitive Docker failure details')
            if not self.keep_remove:
                self.present.remove(args[4])
            return 'Deleted'
        raise AssertionError(args)

    @property
    def removals(self):
        return [args for args in self.calls if args[:3] == ['docker', 'image', 'rm']]


class Store:
    def __init__(self):
        self.reports = []

    def report(self, name, value):
        assert name == gc.REPORT
        self.reports.append(copy.deepcopy(value))


def setup():
    docker, store = Docker(), Store()
    current = gc.capture(docker)
    previous = dict.fromkeys(current, image(2))
    return docker, store, current, previous


def test_only_known_old_image_removed_full_id_no_parent_prune_and_receipt():
    u, store, current, previous = setup()
    report = gc.execute(u, store, current, previous, {image(1), image(2), image(3)}, True)
    assert u.removals == [['docker', 'image', 'rm', '--no-prune', image(3)]]
    assert report['deleted'] == [image(3)] and report['status'] == 'complete'
    assert report['before_bytes'] == 400 and report['after_bytes'] == 300
    assert report['released_bytes'] == 100
    assert report['kept'][image(4)] == ['unknown-or-unpublished-image']
    assert store.reports[0]['status'] == 'cleaning' and store.reports[0]['deleted'] == []
    assert store.reports[-1] == report and gc.DF in u.calls


def test_preview_no_mutation_or_receipt():
    u, store, current, previous = setup()
    report = gc.execute(u, store, current, previous, {image(3)})
    assert report['candidates'] == [image(3)]
    assert report['status'] == 'preview' and not u.removals and not store.reports


def test_current_previous_same_images_do_not_keep_older_distinct_version():
    u, store, current, _ = setup()
    original = copy.deepcopy(current)
    report = gc.execute(u, store, current, current, {image(1), image(2)}, True)
    assert report['deleted'] == [image(2)] and current == original
    again = gc.execute(u, store, current, current, {image(1), image(2)}, True)
    assert again['deleted'] == [] and again['released_bytes'] == 0


def test_stopped_foreign_container_protects_shared_image():
    u, store, current, previous = setup()
    u.rows.append({'Id': 'f' * 64, 'Name': '/other-business', 'Image': image(3),
                   'State': {'Running': False}, 'Config': {'Labels': {}}})
    report = gc.execute(u, store, current, previous, {image(3)}, True)
    assert report['kept'][image(3)] == ['container-reference'] and not u.removals


def test_new_container_reference_between_plan_and_delete_is_protected():
    u, store, current, previous = setup()
    def race(count):
        if count == 3:
            u.rows.append({'Id': 'f' * 64, 'Name': '/new-candidate', 'Image': image(3),
                           'State': {'Running': False}, 'Config': {'Labels': {}}})
    u.on_scan = race
    report = gc.execute(u, store, current, previous, {image(3)}, True)
    assert not u.removals and report['kept'][image(3)] == ['new-container-reference']


def test_deployment_race_stops_before_delete():
    u, store, current, previous = setup()
    u.on_scan = lambda count: u.rows[0].update(Image=image(3)) if count == 3 else None
    report = gc.execute(u, store, current, previous, {image(3)}, True)
    assert not u.removals and report['status'] == 'warning'
    assert report['errors'][0]['stage'] == 'recheck'


@pytest.mark.parametrize('failure', ['fail_remove', 'keep_remove'])
def test_docker_failure_or_success_without_deletion_never_report_deleted(failure):
    u, store, current, previous = setup()
    setattr(u, failure, True)
    report = gc.execute(u, store, current, previous, {image(3)}, True)
    assert report['status'] == 'warning' and report['deleted'] == []
    assert report['released_bytes'] == 0 and image(3) in u.present
    assert 'sensitive' not in json.dumps(report)


@pytest.mark.parametrize('change', ['missing-current', 'missing-previous', 'live-drift', 'incomplete-map'])
def test_invalid_baseline_refuses_all_deletion(change):
    u, store, current, previous = setup()
    if change == 'missing-current':
        u.present.remove(image(1))
    elif change == 'missing-previous':
        u.present.remove(image(2))
    elif change == 'live-drift':
        u.rows[0]['Image'] = image(3)
    else:
        previous.pop(next(iter(previous)))
    with pytest.raises(RuntimeError):
        gc.execute(u, store, current, previous, {image(3)}, True)
    assert not u.removals and not store.reports


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'label', 'name', 'unhealthy',
                                   'stopped', 'paused', 'restarting', 'truncated-image'])
def test_capture_requires_exact_healthy_deployment_inventory(change):
    u = Docker()
    if change == 'missing':
        u.rows.pop()
    elif change == 'duplicate':
        row = copy.deepcopy(u.rows[0])
        row['Id'] = 'f' * 64
        u.rows.append(row)
    elif change == 'label':
        u.rows[0]['Config']['Labels']['com.docker.compose.project'] = 'other'
    elif change == 'name':
        u.rows[0]['Name'] = '/other'
    elif change == 'unhealthy':
        u.rows[0]['State']['Health'] = {'Status': 'unhealthy'}
    elif change == 'stopped':
        u.rows[0]['State']['Running'] = False
    elif change == 'paused':
        u.rows[0]['State']['Paused'] = True
    elif change == 'restarting':
        u.rows[0]['State']['Restarting'] = True
    else:
        u.rows[0]['Image'] = '123456789012'
    with pytest.raises(RuntimeError):
        gc.capture(u)


def test_invalid_history_and_layer_measurement_fail_closed():
    u, store, current, previous = setup()
    with pytest.raises(RuntimeError, match='full image ID'):
        gc.execute(u, store, current, previous, {'bad'}, True)
    original = u.run
    u.run = lambda args: '{"LayersSize":-1}' if args == gc.DF else original(args)
    with pytest.raises(RuntimeError, match='layer size'):
        gc.execute(u, store, current, previous, {image(3)}, True)
    assert not u.removals


def test_retained_image_disappears_before_delete_blocks_cleanup():
    u, store, current, previous = setup()
    u.on_scan = lambda count: u.present.discard(image(2)) if count == 3 else None
    report = gc.execute(u, store, current, previous, {image(3)}, True)
    assert not u.removals and report['status'] == 'warning'


def test_post_delete_inventory_failure_is_warning_not_false_deletion():
    u, store, current, previous = setup()
    original = u.run
    def run(args):
        if args == ['docker', 'image', 'ls', '-aq', '--no-trunc'] and u.removals:
            raise RuntimeError('inventory unavailable')
        return original(args)
    u.run = run
    report = gc.execute(u, store, current, previous, {image(3)}, True)
    assert report['status'] == 'warning' and report['deleted'] == []
    assert 'after_bytes' not in report


def test_shared_layers_use_engine_difference_not_sum_of_image_sizes():
    u, store, current, previous = setup()
    original = u.run
    def run(args):
        if args == gc.DF:
            return json.dumps({'LayersSize': 3435224213 if image(3) in u.present else 3435224200})
        return original(args)
    u.run = run
    report = gc.execute(u, store, current, previous, {image(3)}, True)
    assert report['released_bytes'] == 13
    assert report['bytes_scope'] == 'docker-system-df-LayersSize'


def test_already_absent_candidate_is_not_credited_as_our_deletion():
    u, store, current, previous = setup()
    u.on_scan = lambda count: u.present.discard(image(3)) if count == 3 else None
    report = gc.execute(u, store, current, previous, {image(3)}, True)
    assert not u.removals and report['deleted'] == []
    assert report['kept'][image(3)] == ['already-absent-before-delete']


def test_failed_command_that_removed_image_still_is_not_reported_as_success():
    u, store, current, previous = setup()
    original = u.run
    def run(args):
        result = original(args)
        if args[:3] == ['docker', 'image', 'rm']:
            raise RuntimeError('transport error after server action')
        return result
    u.run = run
    report = gc.execute(u, store, current, previous, {image(3)}, True)
    assert image(3) not in u.present
    assert report['status'] == 'warning' and report['deleted'] == []
    assert report['released_bytes'] == 100
