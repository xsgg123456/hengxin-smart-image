"""Offline failure injection: no SSH, database, Docker or systemd execution."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import engine as e

u = e.u


class EngineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.work, self.systemd, self.compose = root / 'work', root / 'systemd', root / 'compose.json'
        self.work.mkdir()
        self.systemd.mkdir()
        self.old, self.new = b'{"old":true}', b'{"new":true}'
        self.old_dropin = b'[Service]\nWorkingDirectory=/previous/backend\n'
        self.compose.write_bytes(self.old)
        self.ctx = {n: dict(python='/old/python', cwd='/previous/backend', env={'SECRET': 'private'},
                            user=1001, group=1001, extra_groups=[]) for n in u.NATIVE}
        baseline = dict(engine=1, release=str(root / 'release'), release_manifest='manifest',
                        data_containers={'db': 'same-id'}, candidate=u.digest(self.new),
                        native={n: {k: v for k, v in c.items() if k != 'env'} for n, c in self.ctx.items()},
                        configs=[], dropins={})
        paths = [self.compose]
        for name in u.NATIVE:
            directory = self.systemd / (name + '.service.d')
            directory.mkdir()
            path = directory / u.DROPIN
            path.write_bytes(self.old_dropin)
            paths.append(path)
            data = b'[Service]\nWorkingDirectory=/new/backend\n'
            (self.work / (name + '.conf')).write_bytes(data)
            baseline['dropins'][name] = u.digest(data)
        for index, path in enumerate(paths):
            filename = 'backup-' + str(index)
            (self.work / filename).write_bytes(path.read_bytes())
            baseline['configs'].append(dict(path=str(path), backup=filename,
                                             sha256=u.digest(path.read_bytes()), mode=0o600))
        baseline['inventory'] = sorted(str(p) for p in paths)
        (self.work / 'compose.candidate.json').write_bytes(self.new)
        (self.work / 'prepared.json').write_text(json.dumps(baseline))
        self.baseline = baseline
        def write(path, data, mode=0o600, exclusive=False):
            if not path.resolve().is_relative_to(root):
                raise AssertionError('Test write escaped its temporary directory')
            if exclusive and path.exists():
                raise FileExistsError(path)
            path.write_bytes(data)
        self.write = write
        patches = dict(WORK=self.work, RELEASE=root / 'release', SYSTEMD=self.systemd, COMPOSE=self.compose,
                       REUSABLE=True, safe=Mock(), write=Mock(side_effect=write),
                       validate_release=Mock(return_value='manifest'), contexts=Mock(return_value=self.ctx),
                       config_paths=Mock(side_effect=lambda: [p for p in paths if p.exists()]),
                       app_command=Mock(), drain=Mock(), gate_accounts=Mock(), stop_apps=Mock(),
                       start_apps=Mock(), health=Mock(), remove_stop_overrides=Mock(), control=Mock(),
                       containers=Mock(return_value={'api': {'State': {'Running': True}}}),
                       probe_candidate=Mock(), candidate_compose=Mock(return_value={'new': True}),
                       data_identity=Mock(return_value={'db': 'same-id'}),
                       prop=Mock(side_effect=lambda n, k: '0' if k == 'MainPID' else 'inactive'),
                       run=Mock(return_value='[{"State":{"Running":false}}]'))
        self.mocks = patches
        for name, value in patches.items():
            p = patch.object(u, name, value)
            p.start()
            self.addCleanup(p.stop)

    def assert_original(self):
        self.assertEqual(self.compose.read_bytes(), self.old)
        for name in u.NATIVE:
            self.assertEqual(e._dropin(name).read_bytes(), self.old_dropin)

    def test_complete_catalog_accepts_real_recovery_journal_but_rejects_backup_drift(self):
        import catalog
        from types import SimpleNamespace
        def proof(_u, _store, path, kind):
            return dict(path=str(path), kind=kind, identity=[1, 1], dirs=['.'],
                        files={p.name: u.digest(p.read_bytes()) for p in path.iterdir() if p.is_file()})
        self.assertEqual(e.apply(), 'applied')
        current = {'backend': '/old', 'frontend': '/old'}
        data = dict(current=current, previous=None, retention=dict(version=1,
                    current=catalog.record(current, {}), previous=None, artifacts={}))
        item = dict(work=str(self.work), mode='full')
        store = SimpleNamespace()
        with patch.object(catalog.artifact_gc, 'proof', side_effect=proof):
            catalog.add_artifact(u, store, data['retention'], self.work, 'transaction', [str(self.work)])
            self.assertEqual(e.recover(), 'rolled-back')
            self.assert_original()
            catalog.finished_attempt(u, store, data, item)
            self.assertEqual(data['retention']['artifacts'][str(self.work)]['proof']['files']['started.json'],
                             u.digest((self.work/'started.json').read_bytes()))
            (self.work/'backup-0').write_bytes(b'tampered')
            with self.assertRaisesRegex(RuntimeError, 'content drift'):
                catalog.finished_attempt(u, store, data, item)

    def test_prepare_backs_up_existing_dropins_without_switching(self):
        for path in self.work.iterdir():
            path.unlink()
        self.assertEqual(e.prepare(), 'prepared')
        self.assert_original()
        saved = e._read('prepared.json')
        self.assertEqual(len(saved['configs']), 8)
        self.mocks['app_command'].assert_not_called()
        self.mocks['stop_apps'].assert_not_called()

    def test_original_one_shot_still_refuses_existing_dropin(self):
        with patch.object(u, 'REUSABLE', False):
            with self.assertRaisesRegex(RuntimeError, 'Existing maintenance'):
                u.prepare()

    def test_success_replaces_existing_dropins_and_apply_is_idempotent(self):
        self.assertEqual(e.apply(), 'applied')
        self.assertEqual(self.compose.read_bytes(), self.new)
        for name in u.NATIVE:
            self.assertEqual(e._dropin(name).read_bytes(), (self.work / (name + '.conf')).read_bytes())
        calls = self.mocks['app_command'].call_count
        self.assertEqual(e.apply(), 'applied')
        self.assertEqual(self.mocks['app_command'].call_count, calls)

    def test_health_failure_restores_existing_dropin_contents(self):
        self.mocks['start_apps'].side_effect = [RuntimeError('failed health'), None]
        with self.assertRaisesRegex(RuntimeError, 'failed health'):
            e.apply()
        self.assert_original()
        self.assertTrue((self.work / 'rolled-back.json').exists())

    def test_success_can_be_explicitly_rolled_back_once(self):
        e.apply()
        self.assertEqual(e.recover(), 'rolled-back')
        self.assert_original()
        calls = self.mocks['app_command'].call_count
        self.assertEqual(e.recover(), 'rolled-back')
        self.assertEqual(self.mocks['app_command'].call_count, calls)
        with self.assertRaisesRegex(RuntimeError, 'Rolled back'):
            e.apply()

    def test_dirty_config_refuses_before_ingress(self):
        e._dropin(next(iter(u.NATIVE))).write_bytes(b'external config')
        with self.assertRaisesRegex(RuntimeError, 'Configuration drift'):
            e.apply()
        self.mocks['app_command'].assert_not_called()

    def test_corrupt_backup_refuses_before_ingress(self):
        (self.work / 'backup-1').write_bytes(b'corrupt')
        with self.assertRaisesRegex(RuntimeError, 'backup drift'):
            e.apply()
        self.mocks['app_command'].assert_not_called()

    def test_unknown_stop_override_refuses_before_ingress(self):
        e._dropin(next(iter(u.NATIVE))).with_name('91-unify-stop.conf').write_bytes(u.STOP_OVERRIDE)
        with self.assertRaisesRegex(RuntimeError, 'maintenance'):
            e.apply()
        self.mocks['app_command'].assert_not_called()

    def test_extra_unloaded_configuration_refuses(self):
        e._dropin(next(iter(u.NATIVE))).with_name('99-other.conf').write_bytes(b'external')
        with self.assertRaisesRegex(RuntimeError, 'inventory drift'):
            e.apply()
        self.mocks['app_command'].assert_not_called()

    def test_interrupted_partial_switch_recovers_from_disk(self):
        count = 0
        def interrupted(path, data, mode=0o600, exclusive=False):
            nonlocal count
            if path.name == u.DROPIN:
                count += 1
                if count == 3:
                    raise SystemExit('process interrupted')
            self.write(path, data, mode, exclusive)
        self.mocks['write'].side_effect = interrupted
        with patch.object(e, 'recover', side_effect=SystemExit('no cleanup')):
            with self.assertRaisesRegex(RuntimeError, 'RECOVERY_UNCONFIRMED'):
                e.apply()
        self.assertEqual(e._read('started.json')['phase'], 'switching')
        self.mocks['write'].side_effect = self.write
        e.configure(u.RELEASE, self.work)
        with self.assertRaisesRegex(RuntimeError, 'requires recover'):
            e.apply()
        self.assertEqual(e.recover(), 'rolled-back')
        self.assert_original()

    def test_pause_journal_is_written_before_consumer_operation(self):
        def drain(ctx, paused):
            paused.append(u.WORKERS[0])
            self.assertEqual(e._read('started.json')['paused'], [u.WORKERS[0]])
            raise RuntimeError('pause refused')
        self.mocks['drain'].side_effect = drain
        with self.assertRaisesRegex(RuntimeError, 'pause refused'):
            e.apply()
        self.mocks['control'].assert_called_once()
        self.assertEqual(self.mocks['control'].call_args.args[:2], (u.WORKERS[0], 'resume'))
        self.mocks['stop_apps'].assert_not_called()

    def test_busy_recovery_preserves_workers_and_keeps_ingress_closed(self):
        e.apply()
        self.mocks['stop_apps'].reset_mock()
        self.mocks['prop'].side_effect = lambda n, k: 'active' if k == 'ActiveState' else '123'
        self.mocks['drain'].side_effect = RuntimeError('Jobs remain')
        with self.assertRaisesRegex(RuntimeError, 'Jobs remain'):
            e.recover()
        self.mocks['stop_apps'].assert_not_called()
        self.assertEqual(self.mocks['app_command'].call_args.args, ('stop', u.ENTRIES))
        self.assertFalse((self.work / 'rolled-back.json').exists())

    def test_partial_credential_start_is_not_killed(self):
        e.apply()
        self.mocks['stop_apps'].reset_mock()
        self.mocks['prop'].side_effect = lambda n, k: '123' if n == 'hengxin-codex-auth' and k == 'MainPID' else '0'
        with self.assertRaisesRegex(RuntimeError, 'Partial credential'):
            e.recover()
        self.mocks['stop_apps'].assert_not_called()

    def test_recovery_does_not_overwrite_external_compose(self):
        e.apply()
        self.compose.write_bytes(b'another operator')
        with self.assertRaisesRegex(RuntimeError, 'Configuration drift'):
            e.recover()
        self.assertEqual(self.compose.read_bytes(), b'another operator')

    def test_recovery_does_not_claim_success_after_data_identity_changes(self):
        e.apply()
        self.mocks['start_apps'].side_effect = lambda ctx: setattr(self.mocks['data_identity'], 'return_value', {'db': 'changed'})
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            e.recover()
        self.assertFalse((self.work / 'rolled-back.json').exists())

    def test_interrupted_explicit_recovery_cannot_be_mistaken_for_applied(self):
        e.apply()
        self.mocks['app_command'].side_effect = SystemExit('interrupted before stop')
        with self.assertRaises(SystemExit):
            e.recover()
        self.mocks['app_command'].side_effect = None
        with self.assertRaisesRegex(RuntimeError, 'Interrupted recovery'):
            e.apply()
        self.assertEqual(e.recover(), 'rolled-back')
        self.assert_original()

    def test_credential_socket_journal_precedes_gate_and_survives_interrupt(self):
        socket = self.work / 'socket-placeholder'
        socket.write_bytes(b'')
        def gate(sockets):
            sockets.append((socket, socket.stat().st_ino, 0o600))
            self.assertEqual(e._read('started.json')['sockets'][0][0], str(socket))
            raise SystemExit('interrupted during credential gate')
        self.mocks['gate_accounts'].side_effect = gate
        with patch.object(e, 'recover', side_effect=SystemExit('no cleanup')):
            with self.assertRaisesRegex(RuntimeError, 'RECOVERY_UNCONFIRMED'):
                e.apply()
        with patch.object(e, '_restore_sockets') as restore:
            self.assertEqual(e.recover(), 'rolled-back')
        self.assertEqual(restore.call_args.args[0]['sockets'][0][0], str(socket))
        self.mocks['stop_apps'].assert_not_called()


if __name__ == '__main__':
    unittest.main()
