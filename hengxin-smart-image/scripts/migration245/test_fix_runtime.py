"""Deployment fault injection: no network, processes, or live service mutations."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import fix_runtime as f


class RuntimeTransaction(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'candidate'
        self.base.mkdir()
        self.backends = tuple(self.root / s for s in ('domestic', 'overseas'))
        self.account = self.root / 'account'
        self.systemd = self.root / 'systemd'
        self.systemd.mkdir()
        self.original = b'ORIGINAL = True\n'
        self.candidate = b'REPAIRED = True\n'
        self.workspaces = []
        for root in (*self.backends, self.account):
            path = root / 'app/execution/workspace.py'
            path.parent.mkdir(parents=True)
            path.write_bytes(self.original)
            self.workspaces.append(path)
        for name, data in zip(f.NAMES, (self.candidate, b'PROBE = True\n', b'RENDER = True\n')):
            (self.base / name).write_bytes(data)
        self.manifest = self.base / 'candidate-sha256.json'
        self.manifest.write_text(json.dumps({n: f.digest((self.base / n).read_bytes()) for n in f.NAMES}))
        self.env = self.root / 'account.env'
        self.env.write_bytes(b'PRIVATE_TOKEN=do-not-log\n')
        for key, value in dict(BASE=self.base, BACKENDS=self.backends, ACCOUNT_ROOT=self.account,
                               SYSTEMD=self.systemd, ACCOUNT_ENV=self.env,
                               BASELINE_SHA=f.digest(self.original)).items():
            self.patch(key, value)
        self.patch('secure', Mock())  # POSIX ownership is separately checked below.
        self.patch('install', self.install)
        self.patch('identity', Mock(return_value={'user': 123, 'group': 123, 'extra_groups': [456]}))
        self.patch('probes', Mock())
        self.states = {s: 'active' for s in ('worker-a', 'worker-b', 'aux', 'account')}
        self.events = []
        self.installs = []
        self.fail_start = False
        self.m = SimpleNamespace(WORKERS=('worker-a', 'worker-b'), AUX=('aux',), ACCOUNT='account',
                                 SERVICES=tuple(self.states), FILES=[])
        self.m.context = Mock(side_effect=lambda s: (str(self.backends[self.m.WORKERS.index(s)]), {})
                              if s in self.m.WORKERS else ('other', {}))
        self.m.prop = Mock(side_effect=lambda s, k: self.states[s] if k == 'ActiveState'
                           else ('123' if self.states[s] == 'active' else '0'))
        self.m.drain = Mock()
        self.m.gate_account = Mock()
        self.m.run = Mock(side_effect=self.fake_run)
        self.m.verify = Mock(return_value={'ready': True})
        self.m.control = Mock(return_value={'queues': [], 'active': 0, 'reserved': 0, 'scheduled': 0, 'database': 0})

    def patch(self, key, value):
        patcher = patch.object(f, key, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def install(self, path, data, mode, group, exclusive=False, journal=None):
        # Portable transport adapter; real identity/content checks still execute.
        if exclusive and path.exists():
            raise FileExistsError(str(path))
        self.installs.append((path, mode, exclusive))
        path.write_bytes(data)
        if journal is not None:
            journal[path] = f.snapshot(path)
        return f.snapshot(path)

    def fake_run(self, args, **kwargs):
        self.events.append(args)
        if args[:2] == ['systemctl', 'stop']:
            for service in args[2:]:
                self.states[service] = 'inactive'
        if args[:2] == ['systemctl', 'start']:
            for service in args[2:]:
                self.states[service] = 'active'
                if self.fail_start and service == 'worker-a':
                    self.fail_start = False
                    raise RuntimeError('second worker startup failed')
        return SimpleNamespace(stdout='')

    def test_success_preserves_configuration_and_records_absent_backups(self):
        f.transact(self.m)
        self.assertTrue(all(p.read_bytes() == self.candidate for p in self.workspaces))
        self.assertEqual(self.env.read_bytes(), b'PRIVATE_TOKEN=do-not-log\n')
        paths = json.loads((self.base / 'transaction/paths.json').read_text())
        self.assertEqual(sum(x['backup'] is None for x in paths), 7)
        renderers = {r / 'app/execution/office_render.py' for r in (*self.backends, self.account)}
        self.assertEqual({p for p, mode, exclusive in self.installs if mode == 0o755 and exclusive}, renderers)
        self.assertTrue(all(p.read_bytes() == b'RENDER = True\n' for p in renderers))
        f.probes.assert_called_once()
        self.m.verify.assert_called_once()

    def test_bad_source_refuses_before_drain(self):
        self.workspaces[1].write_bytes(b'changed = True\n')
        with self.assertRaisesRegex(RuntimeError, 'baseline drift'):
            f.transact(self.m)
        self.m.drain.assert_not_called()
        self.m.run.assert_not_called()

    def test_candidate_changed_during_drain_never_installed(self):
        def tamper(*args):
            (self.base / f.NAMES[0]).write_bytes(b'changed = True\n')
        self.m.drain.side_effect = tamper
        with self.assertRaisesRegex(RuntimeError, 'Candidate hash mismatch'):
            f.transact(self.m)
        self.assertTrue(all(p.read_bytes() == self.original for p in self.workspaces))
        f.probes.assert_not_called()

    def test_rehashed_candidate_during_drain_also_refused(self):
        def tamper(*args):
            (self.base / f.NAMES[0]).write_bytes(b'changed = True\n')
            self.manifest.write_text(json.dumps({n: f.digest((self.base / n).read_bytes()) for n in f.NAMES}))
        self.m.drain.side_effect = tamper
        with self.assertRaisesRegex(RuntimeError, 'Candidate changed during drain'):
            f.transact(self.m)
        self.assertTrue(all(p.read_bytes() == self.original for p in self.workspaces))

    def test_configuration_drift_during_drain_refused(self):
        self.m.drain.side_effect = lambda *args: self.env.write_bytes(b'NEW_CONFIG=1\n')
        with self.assertRaisesRegex(RuntimeError, 'configuration drift'):
            f.transact(self.m)
        self.assertTrue(all(p.read_bytes() == self.original for p in self.workspaces))
        self.assertEqual(self.env.read_bytes(), b'NEW_CONFIG=1\n')

    def test_workspace_drift_during_drain_never_overwritten(self):
        self.m.drain.side_effect = lambda *args: self.workspaces[0].write_bytes(b'OTHER = True\n')
        with self.assertRaisesRegex(RuntimeError, 'Source/configuration drift'):
            f.transact(self.m)
        self.assertEqual(self.workspaces[0].read_bytes(), b'OTHER = True\n')
        self.assertEqual(self.workspaces[1].read_bytes(), self.original)

    def test_partial_install_failure_restores_already_published_files(self):
        def install_then_fail(path, *args, **kwargs):
            result = self.install(path, *args, **kwargs)
            if path == self.workspaces[1] and kwargs.get('journal') is not None:
                raise OSError('post-publication failure')
            return result
        self.patch('install', install_then_fail)
        with self.assertRaisesRegex(OSError, 'post-publication failure'):
            f.transact(self.m)
        self.assertTrue(all(p.read_bytes() == self.original for p in self.workspaces))

    def test_probe_failure_restores_code_and_removes_only_new_files(self):
        f.probes.side_effect = RuntimeError('sandbox probe failed')
        with self.assertRaisesRegex(RuntimeError, 'sandbox probe failed'):
            f.transact(self.m)
        self.assertTrue(all(p.read_bytes() == self.original for p in self.workspaces))
        self.assertTrue(all(not (b / 'app/execution/runtime_check.py').exists() for b in self.backends))
        self.assertTrue(all(not (b / 'app/execution/office_render.py').exists()
                            for b in (*self.backends, self.account)))
        self.assertFalse(any(self.systemd.iterdir()))
        self.assertTrue(all(s == 'active' for s in self.states.values()))

    def test_partial_start_drains_live_worker_before_rollback_stop(self):
        self.fail_start = True
        with self.assertRaisesRegex(RuntimeError, 'second worker startup failed'):
            f.transact(self.m)
        calls = [(c.args[0], c.args[1]) for c in self.m.control.call_args_list]
        self.assertEqual(calls, [('worker-a', 'pause'), ('worker-a', 'inspect')])
        self.assertTrue(all(p.read_bytes() == self.original for p in self.workspaces))

    def test_uninspectable_partial_start_never_force_stops_or_resumes_worker(self):
        self.fail_start = True
        self.m.control.side_effect = RuntimeError('inspection unavailable')
        with self.assertRaisesRegex(RuntimeError, 'RECOVERY_UNCONFIRMED: inspection unavailable'):
            f.transact(self.m)
        stops = [e for e in self.events if e[:2] == ['systemctl', 'stop']]
        self.assertEqual(len(stops), 1)
        self.assertEqual(self.states['worker-a'], 'active')
        self.assertTrue(all(p.read_bytes() == self.candidate for p in self.workspaces))

    def test_rollback_refuses_to_remove_new_file_modified_by_someone_else(self):
        def conflict(*args):
            (self.backends[0] / 'app/execution/runtime_check.py').write_bytes(b'OTHER = True\n')
            raise RuntimeError('probe failure')
        f.probes.side_effect = conflict
        with self.assertRaisesRegex(RuntimeError, 'RECOVERY_UNCONFIRMED: Source/configuration drift'):
            f.transact(self.m)
        self.assertEqual((self.backends[0] / 'app/execution/runtime_check.py').read_bytes(), b'OTHER = True\n')
        self.assertFalse(any(e[:2] == ['systemctl', 'start'] for e in self.events))

    def test_manifest_arbitrary_target_rejected(self):
        self.manifest.write_text(json.dumps({'/etc/evil': '0' * 64, **json.loads(self.manifest.read_text())}))
        with self.assertRaisesRegex(RuntimeError, 'exactly the reviewed'):
            f.transact(self.m)
        self.m.drain.assert_not_called()

    def test_renderer_missing_from_manifest_refused(self):
        hashes = json.loads(self.manifest.read_text())
        del hashes['office_render.py']
        self.manifest.write_text(json.dumps(hashes))
        with self.assertRaisesRegex(RuntimeError, 'exactly the reviewed'):
            f.transact(self.m)
        self.m.drain.assert_not_called()

    def test_invalid_renderer_syntax_refused_before_drain(self):
        invalid = b'def broken(:\n'
        (self.base / 'office_render.py').write_bytes(invalid)
        hashes = json.loads(self.manifest.read_text())
        hashes['office_render.py'] = f.digest(invalid)
        self.manifest.write_text(json.dumps(hashes))
        with self.assertRaises(SyntaxError):
            f.transact(self.m)
        self.m.drain.assert_not_called()

    def test_verification_failure_cannot_claim_rollback_success(self):
        self.m.verify.side_effect = RuntimeError('queue verification failed')
        with self.assertRaisesRegex(RuntimeError, 'RECOVERY_UNCONFIRMED: queue verification failed'):
            f.transact(self.m)
        self.assertFalse((self.base / 'transaction/applied.json').exists())


class Guards(unittest.TestCase):
    def test_host_guard_precedes_helper_execution(self):
        with patch.object(f.socket, 'gethostname', return_value='public-host'), patch.object(f, 'snapshot') as read:
            with self.assertRaisesRegex(RuntimeError, 'Authorized intranet'):
                f.main()
            read.assert_not_called()

    def test_unsafe_parent_permissions_rejected(self):
        path = Path('/example/source.py')
        file_stat = SimpleNamespace(st_mode=0o100644, st_uid=0, st_nlink=1)
        writable_dir = SimpleNamespace(st_mode=0o40777, st_uid=0, st_nlink=1)
        with patch.object(Path, 'lstat', side_effect=[file_stat, writable_dir]):
            with self.assertRaisesRegex(RuntimeError, 'Unsafe ownership/path'):
                f.secure(path)


if __name__ == '__main__':
    unittest.main()
