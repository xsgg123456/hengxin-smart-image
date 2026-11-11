"""Offline source-release guards and transaction failure injection; no SSH/DB."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import unify_release as u


def compose_fixture():
    service = {'image': 'sha256:fixed', 'environment': {'PRIVATE': 'unchanged'},
               'networks': ['private'], 'ports': [], 'command': ['python', '-m', 'app.main'],
               'volumes': [{'type': 'bind', 'source': '/keep', 'target': '/data', 'read_only': False}]}
    services = {n: copy.deepcopy(service) for n in (*u.APPS, *u.DATA)}
    for n in u.PYTHON_SERVICES:
        services[n]['volumes'].append({'type': 'bind', 'source': '/old/patch.py',
                                      'target': '/app/app/core/config.py', 'read_only': True})
    services['domestic-web']['volumes'].append({'type': 'bind', 'source': '/old/frontend',
                                               'target': '/usr/share/nginx/html', 'read_only': True})
    return {'name': 'hengxin-lan', 'services': services, 'networks': {'private': {}}, 'volumes': {'data': {}}}


class ComposeTests(unittest.TestCase):
    def test_only_source_mounts_change(self):
        original = compose_fixture()
        retained = copy.deepcopy(original)
        result = u.candidate_compose(original)
        self.assertEqual(original, retained)
        for name in u.DATA:
            self.assertEqual(result['services'][name], original['services'][name])
        for name in u.PYTHON_SERVICES:
            old, new = original['services'][name], result['services'][name]
            self.assertEqual({k: v for k, v in old.items() if k != 'volumes'},
                             {k: v for k, v in new.items() if k != 'volumes'})
            self.assertEqual(new['volumes'][0], old['volumes'][0])
            self.assertEqual(new['volumes'][1]['target'], '/app/app')
            self.assertTrue(new['volumes'][1]['read_only'])
            self.assertFalse(new['volumes'][1]['bind']['create_host_path'])
            self.assertEqual(len(new['volumes']), 2)

    def test_unknown_service_rejected(self):
        value = compose_fixture()
        value['services']['unknown-worker'] = {}
        with self.assertRaisesRegex(RuntimeError, 'inventory'):
            u.candidate_compose(value)

    def test_parent_code_mount_rejected(self):
        value = compose_fixture()
        value['services']['identity-api']['volumes'].append({'target': '/app', 'source': '/old'})
        with self.assertRaisesRegex(RuntimeError, 'parent'):
            u.candidate_compose(value)

    def test_data_container_command_refused(self):
        with patch.object(u, 'compose') as call:
            for action in ('up', 'stop'):
                with self.assertRaises(RuntimeError):
                    u.app_command(action, ('domestic-postgres',))
            call.assert_not_called()

    def test_up_never_resolves_dependencies_or_pulls(self):
        with patch.object(u, 'compose') as call:
            u.app_command('up', ('domestic-api',))
            call.assert_called_once_with('up', '-d', '--no-deps', '--pull', 'never', 'domestic-api', candidate=False)

    def test_stop_never_forces_busy_task(self):
        with patch.object(u, 'compose') as call:
            u.app_command('stop', ('domestic-api-image-worker',))
            self.assertEqual(call.call_args.args[:3], ('stop', '--timeout', '-1'))


def empty(queues=None):
    return dict(active=0, reserved=0, scheduled=0, database=0, broker=0, queues=queues or [])


class DrainTests(unittest.TestCase):
    def test_image_worker_is_included(self):
        paused = []
        with patch.object(u, 'control', return_value=empty()) as ctl:
            u.drain({}, paused)
        self.assertEqual(paused, list(u.WORKERS))
        self.assertEqual([c.args[0] for c in ctl.call_args_list if c.args[1] == 'pause'], list(u.WORKERS))

    def test_pending_database_blocks_pause(self):
        state = empty()
        state['database'] = 1
        paused = []
        with patch.object(u, 'control', return_value=state) as ctl, patch.object(u.time, 'monotonic', side_effect=[0, 181]):
            with self.assertRaisesRegex(RuntimeError, 'Jobs remain'):
                u.drain({}, paused)
        self.assertFalse(paused)
        self.assertTrue(all(c.args[1] == 'inspect' for c in ctl.call_args_list))

    def test_queue_race_refuses_switch_but_remembers_resume(self):
        count = 0
        def ctl(name, action, *unused):
            nonlocal count
            count += 1
            return empty(['celery']) if count > 6 else empty()
        paused = []
        with patch.object(u, 'control', side_effect=ctl):
            with self.assertRaisesRegex(RuntimeError, 'race'):
                u.drain({}, paused)
        self.assertEqual(paused, list(u.WORKERS))


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.work, self.systemd, self.compose = root / 'work', root / 'systemd', root / 'compose.json'
        self.work.mkdir()
        self.systemd.mkdir()
        self.old = b'{"old":true}'
        self.new = b'{"new":true}'
        self.compose.write_bytes(self.old)
        (self.work / 'backup-0').write_bytes(self.old)
        (self.work / 'compose.candidate.json').write_bytes(self.new)
        self.ctx = {n: {'python': '/old/python', 'cwd': '/old/backend', 'env': {'PRIVATE': 'do-not-serialize'},
                        'user': 1001, 'group': 1001, 'extra_groups': []} for n in u.NATIVE}
        self.baseline = {'release_manifest': 'manifest', 'candidate': u.digest(self.new), 'data_containers': {'db': 'same-id'},
                         'configs': [{'path': str(self.compose), 'backup': 'backup-0',
                                      'sha256': u.digest(self.old), 'mode': 0o600}],
                         'native': {n: {k: v for k, v in c.items() if k != 'env'} for n, c in self.ctx.items()},
                         'dropins': {}}
        for name in u.NATIVE:
            data = b'[Service]\nWorkingDirectory=/new/backend\n'
            (self.work / (name + '.conf')).write_bytes(data)
            self.baseline['dropins'][name] = u.digest(data)
        (self.work / 'prepared.json').write_text(json.dumps(self.baseline))
        def write(path, data, mode=0o600, exclusive=False):
            if exclusive and path.exists():
                raise FileExistsError(path)
            path.write_bytes(data)
        patches = {
            'WORK': self.work, 'SYSTEMD': self.systemd, 'COMPOSE': self.compose,
            'safe': Mock(), 'write': Mock(side_effect=write), 'validate_release': Mock(return_value='manifest'),
            'contexts': Mock(return_value=self.ctx), 'app_command': Mock(), 'drain': Mock(),
            'gate_accounts': Mock(), 'stop_apps': Mock(), 'start_apps': Mock(),
            'remove_stop_overrides': Mock(), 'control': Mock(return_value=empty()),
            'data_identity': Mock(return_value={'db': 'same-id'}),
            'prop': Mock(side_effect=lambda n, k: '0' if k == 'MainPID' else 'inactive'),
            'run': Mock(return_value='[{"State":{"Running":false}}]'),
        }
        self.mocks = patches
        for key, value in patches.items():
            p = patch.object(u, key, value)
            p.start()
            self.addCleanup(p.stop)

    def test_success_changes_only_compose_and_seven_dropins(self):
        u.apply()
        self.assertEqual(self.compose.read_bytes(), self.new)
        self.assertEqual(len(list(self.systemd.rglob(u.DROPIN))), 7)
        self.assertTrue((self.work / 'applied.json').exists())
        self.assertFalse((self.work / 'rolled-back.json').exists())
        self.assertEqual(self.mocks['start_apps'].call_count, 1)

    def test_health_failure_restores_config_and_dropins(self):
        self.mocks['start_apps'].side_effect = [RuntimeError('health failure'), None]
        with self.assertRaisesRegex(RuntimeError, 'health failure'):
            u.apply()
        self.assertEqual(self.compose.read_bytes(), self.old)
        self.assertFalse(list(self.systemd.rglob(u.DROPIN)))
        self.assertTrue((self.work / 'rolled-back.json').exists())
        self.assertEqual(self.mocks['stop_apps'].call_count, 2)

    def test_configuration_drift_is_rejected_before_ingress_stop(self):
        self.compose.write_bytes(b'other deployment')
        with self.assertRaisesRegex(RuntimeError, 'Configuration drift'):
            u.apply()
        self.mocks['app_command'].assert_not_called()

    def test_changed_backup_is_rejected_before_ingress_stop(self):
        (self.work / 'backup-0').write_bytes(b'tampered')
        with self.assertRaisesRegex(RuntimeError, 'backup drift'):
            u.apply()
        self.mocks['app_command'].assert_not_called()

    def test_repeat_transaction_is_refused(self):
        (self.work / 'started.json').write_bytes(b'{}')
        with self.assertRaisesRegex(RuntimeError, 'Existing transaction'):
            u.apply()
        self.mocks['app_command'].assert_not_called()

    def test_data_recreation_is_rejected_before_ingress_stop(self):
        self.mocks['data_identity'].return_value = {'db': 'different-id'}
        with self.assertRaisesRegex(RuntimeError, 'Data container identity drift'):
            u.apply()
        self.mocks['app_command'].assert_not_called()

    def test_drain_failure_restores_ingress_without_stopping_workers(self):
        self.mocks['drain'].side_effect = RuntimeError('busy')
        with self.assertRaisesRegex(RuntimeError, 'busy'):
            u.apply()
        self.mocks['stop_apps'].assert_not_called()
        self.assertEqual(self.compose.read_bytes(), self.old)
        self.assertEqual(self.mocks['app_command'].call_args.args, ('up', u.ENTRIES))

    def test_candidate_drift_during_drain_restores_previous_release(self):
        self.mocks['validate_release'].side_effect = ['manifest', 'changed']
        with self.assertRaisesRegex(RuntimeError, 'Release drift'):
            u.apply()
        self.assertEqual(self.compose.read_bytes(), self.old)
        self.assertFalse(list(self.systemd.rglob(u.DROPIN)))

    def test_rollback_does_not_overwrite_concurrent_compose_change(self):
        def fail(ctx):
            self.compose.write_bytes(b'another operator')
            raise RuntimeError('failed health')
        self.mocks['start_apps'].side_effect = fail
        with self.assertRaisesRegex(RuntimeError, 'RECOVERY_UNCONFIRMED'):
            u.apply()
        self.assertEqual(self.compose.read_bytes(), b'another operator')
        self.assertFalse((self.work / 'rolled-back.json').exists())

    def test_partial_worker_start_must_drain_before_second_stop(self):
        events = []
        self.mocks['start_apps'].side_effect = [RuntimeError('health'), None]
        self.mocks['prop'].side_effect = lambda n, k: 'active' if k == 'ActiveState' and n in u.WORKERS[:2] else '0'
        self.mocks['stop_apps'].side_effect = lambda: events.append('stop')
        self.mocks['drain'].side_effect = lambda *args: events.append('drain')
        with self.assertRaisesRegex(RuntimeError, 'health'):
            u.apply()
        self.assertEqual(events, ['drain', 'stop', 'drain', 'stop'])


if __name__ == '__main__':
    unittest.main()
