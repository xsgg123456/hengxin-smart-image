"""Real engine journal/recovery with scoped process adapters, fully offline."""
import json
import time
import unittest
from unittest.mock import Mock, patch

import engine as e
import scope_engine
import scopes
from scope_actions import Actions
import test_engine

u = e.u
REAL = {n: getattr(u, n) for n in ('app_command', 'stop_apps', 'remove_stop_overrides', 'drain', 'control')}


class ScopeEngineTests(unittest.TestCase):
    def setUp(self):
        test_engine.EngineTests.setUp(self)
        self.commands, self.controls = [], []
        self.active = set(u.NATIVE)
        services = {n: {'image': 'unchanged', 'volumes': []} for n in (*u.APPS, *scopes.UI.values(), *u.DATA)}
        for name in u.PYTHON_SERVICES:
            services[name]['volumes'] = [{'type': 'bind', 'source': '/old/backend/app',
                                          'target': '/app/app', 'read_only': True}]
        for name in ('domestic-web', *scopes.UI.values()):
            services[name]['volumes'] = [{'type': 'bind', 'source': '/old/frontend',
                                          'target': '/usr/share/nginx/html', 'read_only': True}]
        self.old_compose = {'name': 'hengxin-lan', 'services': services}
        self.compose.write_text(json.dumps(self.old_compose))
        for path in self.work.iterdir():
            path.unlink()
        self.mocks['contexts'].side_effect = lambda: {n: self.ctx[n] for n in u.NATIVE}
        self.mocks['containers'].side_effect = lambda: {n: {'State': {'Running': True}} for n in u.APPS}
        self.mocks['prop'].side_effect = lambda n, k: ('active' if n in self.active else 'inactive') if k == 'ActiveState' else ('123' if n in self.active else '0')
        self.mocks['run'].side_effect = self.run_command
        self.mocks['control'].side_effect = self.control
        for name in ('app_command', 'stop_apps', 'remove_stop_overrides', 'drain'):
            p = patch.object(u, name, REAL[name])
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(u, 'native_run', Mock(return_value='{}'))
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(Actions, '_http', Mock())
        p.start()
        self.addCleanup(p.stop)

    def run_command(self, argv, **kwargs):
        self.commands.append(argv)
        if argv[:2] == ['systemctl', 'stop']:
            self.active.difference_update(argv[2:])
        elif argv[:2] == ['systemctl', 'start']:
            self.active.update(argv[2:])
        if argv[:2] == ['systemctl', 'start'] or (argv[:2] == ['docker', 'compose'] and 'up' in argv):
            self.paused.difference_update(argv)
        if argv[:2] == ['docker', 'inspect']:
            return '[{"State":{"Running":true}}]'
        return ''

    def control(self, name, action, ctx, deadline):
        self.controls.append((name, action))
        if action == 'pause':
            self.paused.add(name)
        if action == 'resume':
            self.paused.discard(name)
        return dict(active=0, reserved=0, scheduled=0, database=0, broker=0,
                    queues=[] if name in self.paused else [scopes.QUEUES[name]])

    def prepare(self, scope, mode='full'):
        self.paused = set()
        e.prepare()
        self.commands.clear()
        self.controls.clear()

    def assert_boundaries(self, scope, mode='full'):
        apps = set(scopes.APPS[scope]) if mode == 'full' else set()
        apps.add(scopes.UI[scope])
        native = set(scopes.NATIVE[scope]) if mode == 'full' else set()
        for argv in self.commands:
            if argv[:2] in (['systemctl', 'stop'], ['systemctl', 'start']):
                self.assertTrue(set(argv[2:]) <= native, argv)
                self.assertTrue(argv[2:], argv)
            if argv[:2] == ['docker', 'compose']:
                self.assertNotIn('domestic-web', argv)
                self.assertFalse((set(argv) & (set(self.old_compose['services']) - apps)), argv)
        if scope != 'shared':
            self.assertTrue(all(n in scopes.WORKERS[scope] for n, _ in self.controls))
            self.mocks['gate_accounts'].assert_not_called()

    def test_full_apply_and_explicit_recovery_only_touch_target(self):
        # Each scope has a fresh fixture because journals are intentionally single-use.
        for scope in ('domestic', 'overseas'):
            with self.subTest(scope=scope):
                if (self.work / 'prepared.json').exists():
                    for path in self.work.iterdir():
                        path.unlink()
                with scope_engine.context(scope):
                    self.prepare(scope)
                    # Real worker restart restores default queue subscriptions.
                    original_run = self.mocks['run'].side_effect
                    def restarted(argv, **kw):
                        if argv[:2] == ['systemctl', 'start'] or 'up' in argv:
                            self.paused.clear()
                        return original_run(argv, **kw)
                    self.mocks['run'].side_effect = restarted
                    self.assertEqual(e.apply(), 'applied')
                    changed = json.loads(self.compose.read_bytes())
                    for n in set(self.old_compose['services']) - set(scopes.APPS[scope]) - {scopes.UI[scope]}:
                        self.assertEqual(changed['services'][n], self.old_compose['services'][n])
                    self.assertEqual(e.recover(), 'rolled-back')
                    self.assertEqual(json.loads(self.compose.read_bytes()), self.old_compose)
                    self.assert_boundaries(scope)
                    self.mocks['run'].side_effect = original_run

    def test_frontend_failure_uses_real_engine_recovery_without_backend_actions(self):
        with scope_engine.context('domestic', 'frontend'):
            self.prepare('domestic', 'frontend')
            original = u.start_apps
            calls = 0
            def fail_once(ctx):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError('injected startup failure')
                original(ctx)
            with patch.object(u, 'start_apps', side_effect=fail_once):
                with self.assertRaisesRegex(RuntimeError, 'injected startup'):
                    e.apply()
            self.assertEqual(json.loads(self.compose.read_bytes()), self.old_compose)
            self.assertTrue((self.work / 'rolled-back.json').exists())
            self.assert_boundaries('domestic', 'frontend')
            self.assertFalse(self.controls)
            self.assertFalse(any(cmd[0] == 'systemctl' for cmd in self.commands))

    def test_drain_failure_restores_only_own_ingress_and_consumer(self):
        with scope_engine.context('domestic'):
            self.prepare('domestic')
            def fail(ctx, paused, live=None):
                paused.append(scopes.WORKERS['domestic'][0])
                raise RuntimeError('drain refused')
            with patch.object(u, 'drain', side_effect=fail):
                with self.assertRaisesRegex(RuntimeError, 'drain refused'):
                    e.apply()
            self.assertFalse(any(cmd[:2] == ['systemctl', 'stop'] for cmd in self.commands))
            self.assertEqual(self.controls[0], (scopes.WORKERS['domestic'][0], 'resume'))
            self.assert_boundaries('domestic')

    def test_wrong_frontend_scope_refuses_before_any_mutation(self):
        with scope_engine.context('domestic', 'frontend'):
            self.prepare('domestic', 'frontend')
        with scope_engine.context('overseas', 'frontend'):
            with self.assertRaisesRegex(RuntimeError, 'scope binding'):
                e.apply()
        self.assertEqual(self.commands, [])

    def test_full_health_failure_restores_target_and_preserves_other_dropins(self):
        other = {n: e._dropin(n).read_bytes() for n in u.NATIVE if n not in scopes.NATIVE['domestic']}
        with scope_engine.context('domestic'):
            self.prepare('domestic')
            start = u.start_apps
            calls = 0
            def fail_once(ctx):
                nonlocal calls
                calls += 1
                start(ctx)
                if calls == 1:
                    raise RuntimeError('injected post-start health failure')
            with patch.object(u, 'start_apps', side_effect=fail_once):
                with self.assertRaisesRegex(RuntimeError, 'post-start health failure'):
                    e.apply()
            self.assertEqual(e.recover(), 'rolled-back')
            self.assertEqual(json.loads(self.compose.read_bytes()), self.old_compose)
            self.assert_boundaries('domestic')
        self.assertEqual(other, {n: e._dropin(n).read_bytes() for n in other})

    def test_interrupted_full_switch_recovers_under_fresh_scope_context(self):
        with scope_engine.context('domestic'):
            self.prepare('domestic')
            count = 0
            def interrupted(path, data, mode=0o600, exclusive=False):
                nonlocal count
                if path.name == u.DROPIN:
                    count += 1
                    if count == 2:
                        raise SystemExit('interrupted scoped switch')
                self.write(path, data, mode, exclusive)
            self.mocks['write'].side_effect = interrupted
            with patch.object(e, 'recover', side_effect=SystemExit('process stopped')):
                with self.assertRaisesRegex(RuntimeError, 'RECOVERY_UNCONFIRMED'):
                    e.apply()
            self.assertEqual(e._read('started.json')['phase'], 'switching')
        self.mocks['write'].side_effect = self.write
        with scope_engine.context('domestic'):
            self.assertEqual(e.recover(), 'rolled-back')
            self.assertEqual(json.loads(self.compose.read_bytes()), self.old_compose)
            self.assert_boundaries('domestic')

    def test_shared_busy_refuses_without_gate_or_pausing_any_worker(self):
        self.paused = set()
        def busy(name, action, ctx, deadline):
            result = self.control(name, action, ctx, deadline)
            result['active'] = 1
            return result
        self.mocks['control'].side_effect = busy
        actions = Actions(u, 'shared', 'full', {'contexts': u.contexts}, u.NATIVE, u.RELEASE)
        with self.assertRaisesRegex(RuntimeError, 'both business queues idle'):
            actions.shared_idle()
        self.mocks['gate_accounts'].assert_not_called()
        self.assertTrue(all(action == 'inspect' for _, action in self.controls))
        self.assertFalse(any(cmd[:2] == ['systemctl', 'stop'] for cmd in self.commands))

    def test_control_preserves_overseas_mapping_and_image_exec(self):
        with scope_engine.context('overseas'):
            with patch.object(u, 'native_run', return_value='{}') as native:
                REAL['control']('hengxin-overseas-worker', 'inspect', self.ctx, time.monotonic() + 30)
                self.assertEqual(native.call_args.kwargs['args'][0], 'overseas')
        self.assertEqual(u.WORKERS, ('hengxin-vps-codex-worker', 'hengxin-overseas-worker', 'domestic-api-image-worker'))

    def test_shared_full_refuses_before_any_transaction_or_process_action(self):
        with self.assertRaisesRegex(RuntimeError, 'separate joint maintenance plan'):
            with scope_engine.context('shared'):
                e.prepare()
        self.assertEqual(self.commands, [])
        self.assertEqual(self.controls, [])
        self.assertFalse((self.work / 'prepared.json').exists())

    def test_shared_frontend_only_restarts_its_static_service(self):
        with scope_engine.context('shared', 'frontend'):
            self.prepare('shared', 'frontend')
            self.assertEqual(e.apply(), 'applied')
            self.assertEqual(e.recover(), 'rolled-back')
            self.assert_boundaries('shared', 'frontend')
            self.assertFalse(self.controls)
            self.mocks['gate_accounts'].assert_not_called()
            self.assertEqual(json.loads(self.compose.read_bytes()), self.old_compose)

    def test_rollback_candidate_changes_target_to_distinct_backend_and_frontend(self):
        from pathlib import Path
        candidate = scope_engine.candidate(self.old_compose, u, 'domestic', 'full',
                                           Path('/old-domestic-code'), Path('/old-domestic-ui'))
        changed = candidate['services']
        self.assertEqual(changed['domestic-api']['volumes'][-1]['source'], str(Path('/old-domestic-code/backend/app')))
        self.assertEqual(changed['domestic-ui']['volumes'][0]['source'], str(Path('/old-domestic-ui/frontend')))
        for name in set(changed) - set(scopes.APPS['domestic']) - {scopes.UI['domestic']}:
            self.assertEqual(changed[name], self.old_compose['services'][name])


if __name__ == '__main__':
    unittest.main()
