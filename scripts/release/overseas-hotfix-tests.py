"""Offline unittest mocks for the no-migration overseas-only hotfix."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('hotfix_tests', Path(__file__).with_name('overseas-hotfix-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def save(path, value):
    Path(path).write_text(value if isinstance(value, str) else json.dumps(value))


def empty():
    return dict(workers={'overseas': {'states': [{'node': []} for _ in range(3)],
        'queues': {'overseas.cli': 0}, 'unacked': 0}}, jobs=0, deleting=0)


class HotfixTests(unittest.TestCase):
    def test_optimized_python_aborts_before_production_actions(self):
        script = Path(__file__).with_name('overseas-hotfix-deploy.py')
        for flags, optimize in ((['-O'], '0'), ([], '1')):
            with self.subTest(flags=flags, optimize=optimize):
                result = subprocess.run([sys.executable, *flags, str(script),
                    'overseas-20261014-abcdef0', 'build'], capture_output=True, text=True,
                    env={**os.environ, 'PYTHONOPTIMIZE': optimize}, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('RuntimeError: Python -O disables release safety assertions', result.stderr)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.mock(d.m, 'private', side_effect=save)

    def mock(self, obj, name, **kwargs):
        patcher = patch.object(obj, name, **kwargs)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def setup_deploy(self, failure=None):
        work = self.root / 'work'
        work.mkdir()
        for name in ('PREPARED', 'INSTALL_TEST_IMAGE_ID'):
            (work / name).write_text('sha256:tested')
        data = {group: {'group': group} for group in d.m.GROUPS}
        save(work / 'topology.json', data)
        save(work / 'domestic-native.json', {'pid': 123, 'cwd': '/old/domestic'})
        (work / 'native-target').write_text('/new/overseas/backend')
        edge = self.root / 'edge.conf'
        edge.write_text('location ^~ /api/overseas/v1/ { proxy_pass http://overseas; }')
        events = []

        def event(name, *args):
            events.append((name, *args))
            if name == failure:
                raise RuntimeError(name)

        self.mock(d, 'BACKUPS', new=self.root / 'backups')
        self.mock(d.m, 'APP', new=self.root)
        self.mock(d.m, 'EDGE', new=edge)
        self.mock(d.m, 'image_id', return_value='sha256:tested')
        self.mock(d.m, 'topology', return_value=data)
        self.mock(d, 'domestic_native', return_value={'pid': 123, 'cwd': '/old/domestic'})
        self.mock(d, 'schemas')
        self.mock(d, 'prepared_settings', side_effect=lambda *a: event('settings'))
        self.mock(d.m, 'assets_safe', side_effect=lambda *a: event('assets'))
        self.mock(d.r, 'hashes')
        self.mock(d, 'close_edge', side_effect=lambda *a: event('close'))
        self.mock(d, 'closed', side_effect=lambda: event('closed'))
        self.mock(d, 'drain_and_stop', side_effect=lambda *a: event('drain'))
        self.mock(d.m, 'compose', side_effect=lambda data, *a, **kw: event('compose', data['group'], *a))
        self.mock(d.m, 'run', side_effect=lambda *a, **kw: event('run', *a))

        def backup(work, destination, data):
            event('backup')
            destination.mkdir(parents=True)
            (destination / 'COMPLETE').write_text('verified')

        self.mock(d.u, 'backup', side_effect=backup)
        self.mock(d.u, 'switch_native', side_effect=lambda *a: event('switch'))
        self.mock(d.u, 'reload_edge', side_effect=lambda: event('open'))
        self.mock(d, 'installed', side_effect=lambda *a: event('installed'))
        self.mock(d, 'resources_unchanged', side_effect=lambda *a: event('resources'))
        self.mock(d.r, 'publish', side_effect=lambda *a: event('publish'))
        for name in ('proxy', 'frontend', 'public'):
            self.mock(d.verify, name, side_effect=lambda *a, name=name: event(name))
        return work, data, events

    def deploy(self, work):
        d.deploy(work, self.root, {'release': 'fixture', 'files': {}}, 'image')

    def test_success_order_and_only_overseas_mutation(self):
        work, _, events = self.setup_deploy()
        self.deploy(work)
        names = [e[0] for e in events]
        order = ['close', 'closed', 'drain', 'backup', 'switch', 'installed', 'proxy',
                 'publish', 'frontend', 'open', 'public', 'resources']
        self.assertEqual([names.index(n) for n in order], sorted(names.index(n) for n in order))
        commands = [e for e in events if e[0] == 'compose']
        self.assertEqual(commands[0], ('compose', 'overseas', 'stop', '-t', '30', 'api'))
        self.assertTrue(all(e[1] == 'overseas' for e in commands))
        self.assertTrue(all('--no-deps' in e and '--no-build' in e for e in commands if 'up' in e))
        self.assertNotIn('migrate', str(events))
        self.assertNotIn('skills_install', str(events))
        self.assertNotIn('restore', str(events))
        self.assertEqual([e for e in events if e[:2] == ('run', 'systemctl')],
                         [('run', 'systemctl', 'start', *d.u.UNITS)])
        self.assertEqual([e for e in events if 'nginx' in e], [
            ('run', 'docker', 'exec', d.r.PREFIX + 'web-1', 'nginx', '-t'),
            ('run', 'docker', 'exec', d.r.PREFIX + 'web-1', 'nginx', '-s', 'reload')])
        self.assertTrue((work / 'verification.json').exists())
        self.assertTrue((self.root / 'OVERSEAS_RELEASE.json').exists())
        self.assertFalse((self.root / 'MEMBER_RELEASE.json').exists())

    def test_every_cutover_failure_recloses_without_executor_stop(self):
        for failure in ('close', 'closed', 'drain', 'backup', 'switch', 'installed', 'proxy',
                        'publish', 'frontend', 'open', 'public', 'resources'):
            with self.subTest(failure=failure):
                # A separate TestCase keeps all patches and files isolated per failure.
                case = HotfixTests()
                case.setUp()
                try:
                    work, _, events = case.setup_deploy(failure)
                    with self.assertRaisesRegex(RuntimeError, failure):
                        case.deploy(work)
                    self.assertIn(('close',), events[-3:])
                    self.assertEqual(events[-1], ('compose', 'overseas', 'stop', '-t', '30', 'api'))
                    self.assertFalse(any(e[:3] == ('run', 'systemctl', 'stop') for e in events))
                    self.assertNotIn('restore', str(events))
                    self.assertTrue((work / 'FAILURE.json').exists())
                    self.assertFalse((work / 'verification.json').exists())
                finally:
                    case.doCleanups()

    def test_topology_drift_blocks_all_cutover_mutations(self):
        work, _, events = self.setup_deploy()
        d.m.topology.return_value = {'drift': True}
        with self.assertRaisesRegex(AssertionError, 'drift'):
            self.deploy(work)
        self.assertEqual(events, [])
        self.assertFalse((work / 'DEPLOY_STARTED').exists())

    def test_failed_attempt_must_not_be_replayed(self):
        work, _, events = self.setup_deploy()
        (work / 'DEPLOY_STARTED').write_text('failed')
        with self.assertRaisesRegex(AssertionError, 'recovery'):
            self.deploy(work)
        self.assertEqual(events, [])

    def test_drain_busy_and_unknown_never_look_idle(self):
        for fault in ('jobs', 'deleting', 'active', 'reserved', 'scheduled', 'queued', 'unacked', 'unknown'):
            with self.subTest(fault=fault):
                result = empty()
                worker = result['workers']['overseas']
                if fault in ('jobs', 'deleting'):
                    result[fault] = 1
                elif fault in ('active', 'reserved', 'scheduled'):
                    worker['states'][('active', 'reserved', 'scheduled').index(fault)]['node'] = ['work']
                elif fault == 'queued':
                    worker['queues']['overseas.cli'] = 1
                elif fault == 'unacked':
                    worker['unacked'] = 1
                else:
                    worker['states'][0] = None
                with patch.object(d, 'evidence', return_value=result), patch.object(d.m, 'run') as run:
                    with self.assertRaises((AssertionError, RuntimeError)):
                        d.wait_empty(self.root, 'busy', timeout=0)
                    run.assert_not_called()

    def test_drain_requires_two_consecutive_empty_samples(self):
        busy = empty()
        busy['deleting'] = 1
        probe = self.mock(d, 'evidence', side_effect=[empty(), busy, empty(), empty()])
        sleep = self.mock(d.time, 'sleep')
        d.wait_empty(self.root, 'stable')
        self.assertEqual(probe.call_count, 4)
        self.assertEqual(sleep.call_count, 3)

    def test_second_drain_failure_keeps_worker_running(self):
        events = []

        def wait(work, label):
            events.append(label)
            if label == 'drained-after-outbox-stop':
                raise RuntimeError('late publication')

        self.mock(d, 'wait_empty', side_effect=wait)
        self.mock(d.m, 'run', side_effect=lambda *a: events.append(a))
        with self.assertRaisesRegex(RuntimeError, 'late publication'):
            d.drain_and_stop(self.root)
        self.assertEqual(events, ['drained-before-outbox-stop',
            ('systemctl', 'stop', d.u.UNITS[1]), 'drained-after-outbox-stop'])

    def test_drain_stops_only_after_both_stable_checks(self):
        events = []
        self.mock(d, 'wait_empty', side_effect=lambda work, label: events.append(label))
        self.mock(d.m, 'run', side_effect=lambda *a: events.append(a))
        self.mock(d.u, 'pending', return_value=0)
        query = self.mock(d.u, 'sql', return_value='0')
        d.drain_and_stop(self.root)
        self.assertEqual(events, ['drained-before-outbox-stop', ('systemctl', 'stop', d.u.UNITS[1]),
            'drained-after-outbox-stop', ('systemctl', 'stop', d.u.UNITS[0])])
        query.assert_called_once_with("SELECT count(*) FROM overseas_task_deletions WHERE status='deleting'")

    def test_close_edge_preserves_domestic_and_identity(self):
        other = 'location ^~ /api/v1/ { proxy_pass http://domestic; }\n'
        other += 'location ^~ /api/identity/v1/ { proxy_pass http://identity; }\n'
        result = d.closed_config(other + 'location ^~ /api/overseas/v1/ { proxy_pass http://overseas; }')
        self.assertEqual(result, other + 'location ^~ /api/overseas/v1/ { return 503; }')
        self.assertEqual(d.closed_config(result), result)
        with self.assertRaises(AssertionError):
            d.closed_config(other)

    def test_closed_waits_for_reload_and_times_out_if_still_open(self):
        status = self.mock(d.verify, 'status', side_effect=['401', '503', '503', '503'])
        sleep = self.mock(d.time, 'sleep')
        d.closed()
        self.assertEqual(status.call_count, 4)
        sleep.assert_called_once_with(1)
        status.side_effect = None
        status.return_value = '401'
        with self.assertRaisesRegex(AssertionError, 'not closed'):
            d.closed(timeout=0)

    def test_prepared_overlay_allows_only_api_image_build(self):
        source, image = self.root / 'src', 'sha256:test'
        baseline = {'services': {'api': {'image': 'old', 'volumes': [{'target': '/skills', 'read_only': True}]},
                                 'migrate': {'image': 'old'}}}
        overlay = {'services': {'api': {'image': image, 'build': {
            'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}}}}
        save(self.root / 'overseas-overlay.json', overlay)
        save(self.root / 'overseas-compose.private.json', baseline)
        after = copy.deepcopy(baseline)
        after['services']['api'].update(overlay['services']['api'])
        compose = self.mock(d.m, 'compose', side_effect=[json.dumps(baseline), json.dumps(after)])
        d.prepared_settings(self.root, {'overseas': {}}, image, source)
        after['services']['api']['volumes'][0]['read_only'] = False
        compose.side_effect = [json.dumps(baseline), json.dumps(after)]
        with self.assertRaisesRegex(AssertionError, 'settings'):
            d.prepared_settings(self.root, {'overseas': {}}, image, source)
        overlay['services']['migrate'] = {'image': image}
        save(self.root / 'overseas-overlay.json', overlay)
        with self.assertRaisesRegex(AssertionError, 'overlay drift'):
            d.prepared_settings(self.root, {'overseas': {}}, image, source)

    def test_resource_checks_detect_domestic_restart_and_overseas_mount_change(self):
        native = {'pid': 123, 'cwd': '/domestic'}
        data = {group: {'ids': {}, 'mounts': {}, 'files': {}} for group in d.m.GROUPS}
        data['domestic']['ids'] = {'domestic-api': 'original'}
        data['overseas'].update(ids={d.u.API: 'old-api', 'redis': 'old-redis'},
            mounts={d.u.API: [{'Destination': '/skills', 'RW': False}]}, paths=['old.yml'],
            project='overseas', cwd='/cwd', env='old.env')
        data.update(native={d.m.UNITS[0]: '/domestic', **{u: '/old' for u in d.u.UNITS}}, nativeFiles={})
        target = {'native': Path('/new'), 'overlay': Path('/new-overlay')}
        current = copy.deepcopy(data)
        current['overseas']['paths'].append(str(target['overlay']))
        current['overseas']['ids'][d.u.API] = 'new-api'
        current['native'].update({u: str(target['native']) for u in d.u.UNITS})
        self.mock(d, 'domestic_native', return_value=native)
        topology = self.mock(d.m, 'topology', return_value=current)
        d.resources_unchanged(data, native, target)
        for fault in ('domestic', 'redis', 'mount', 'native'):
            changed = copy.deepcopy(current)
            if fault == 'domestic': changed['domestic']['ids']['domestic-api'] = 'new'
            if fault == 'redis': changed['overseas']['ids']['redis'] = 'new'
            if fault == 'mount': changed['overseas']['mounts'][d.u.API][0]['RW'] = True
            if fault == 'native': changed['nativeFiles']['unexpected.conf'] = 'new'
            topology.return_value = changed
            with self.subTest(fault=fault), self.assertRaises(AssertionError):
                d.resources_unchanged(data, native, target)


if __name__ == '__main__':
    unittest.main()
