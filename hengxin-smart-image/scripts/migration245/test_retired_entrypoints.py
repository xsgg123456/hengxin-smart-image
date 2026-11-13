"""Offline retirement checks: no SSH, subprocesses, or deployment writes."""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import runpy
import unittest
from unittest.mock import Mock, patch

try:
    import paramiko
except ModuleNotFoundError:
    paramiko = None
import transport
import unify_release


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
GUIDANCE = 'scripts/release/intranet/release.py --scope'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TransportTests(unittest.TestCase):
    def test_old_source_calls_fail_before_ssh_client_creation(self):
        for value in (True, 1, 'source', None):
            with self.subTest(value=value):
                with patch('builtins.__import__', side_effect=AssertionError('SSH dependency imported')) as imports:
                    with self.assertRaisesRegex(RuntimeError, 'migration is retired'):
                        transport.connect(value)
                    with self.assertRaisesRegex(RuntimeError, 'migration is retired'):
                        transport.connect(source=value)
                    imports.assert_not_called()

    @unittest.skipUnless(paramiko, 'SSH mock checks require paramiko; retirement checks remain active')
    def test_default_and_explicit_false_connect_only_to_verified_intranet(self):
        for args in ((), (False,)):
            with self.subTest(args=args), patch.object(paramiko, 'SSHClient') as ssh:
                client = ssh.return_value
                client.exec_command.return_value = (Mock(), Mock(), Mock())
                client.exec_command.return_value[1].read.return_value = b'hengxin-ai-245\n'
                self.assertIs(transport.connect(*args), client)
                client.load_system_host_keys.assert_called_once_with()
                policy = client.set_missing_host_key_policy.call_args.args[0]
                self.assertIsInstance(policy, paramiko.RejectPolicy)
                client.connect.assert_called_once_with(
                    '192.168.1.245', username='root',
                    key_filename=str(Path.home() / '.ssh' / 'hengxin_devhub_prod'),
                    allow_agent=False, look_for_keys=False, timeout=15,
                    banner_timeout=15, auth_timeout=15, channel_timeout=60)
                client.exec_command.assert_called_once_with('hostname', timeout=60)
                client.get_transport.return_value.set_keepalive.assert_called_once_with(20)

    @unittest.skipUnless(paramiko, 'SSH mock checks require paramiko; retirement checks remain active')
    def test_wrong_hostname_closes_client(self):
        with patch.object(paramiko, 'SSHClient') as ssh:
            client = ssh.return_value
            client.exec_command.return_value = (Mock(), Mock(), Mock())
            client.exec_command.return_value[1].read.return_value = b'wrong-host\n'
            with self.assertRaisesRegex(RuntimeError, 'host identity mismatch'):
                transport.connect()
            client.close.assert_called_once_with()
            client.get_transport.assert_not_called()

    @unittest.skipUnless(paramiko, 'SSH mock checks require paramiko; retirement checks remain active')
    def test_untrusted_host_key_is_not_bypassed(self):
        with patch.object(paramiko, 'SSHClient') as ssh:
            client = ssh.return_value
            client.connect.side_effect = paramiko.SSHException('untrusted host key')
            with self.assertRaisesRegex(paramiko.SSHException, 'untrusted host key'):
                transport.connect()
            client.exec_command.assert_not_called()

    def test_source_transfer_api_is_removed(self):
        self.assertFalse(hasattr(transport, 'transfer'))
        self.assertFalse(hasattr(transport, 'destination_path'))


class RetiredEntryTests(unittest.TestCase):
    def guarded(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        targets = ('socket.create_connection', 'subprocess.run', 'subprocess.check_output',
                   'pathlib.Path.mkdir', 'pathlib.Path.write_bytes')
        if paramiko:
            targets += ('paramiko.SSHClient',)
        mocks = [stack.enter_context(patch(target, side_effect=AssertionError(target)))
                 for target in targets]
        return mocks

    def test_cli_refuses_every_form_without_side_effects(self):
        guards = self.guarded()
        for script, arguments in (
            ('transport.py', []),
            ('transport.py', ['collect_runtime.py', 'runtime.tar']),
            ('unify_release.py', []),
            ('unify_release.py', ['--help']),
            *(('unify_release.py', [action]) for action in ('preflight', 'prepare', 'apply')),
        ):
            with self.subTest(script=script, arguments=arguments), patch('sys.argv', [script, *arguments]):
                with self.assertRaises(SystemExit) as refused:
                    runpy.run_path(str(HERE / script), run_name='__main__')
                self.assertIn(GUIDANCE, str(refused.exception))
                self.assertNotEqual(refused.exception.code, 0)
        for guard in guards:
            guard.assert_not_called()

    def test_imported_main_cannot_dispatch_whole_site_actions(self):
        with ExitStack() as stack:
            actions = [stack.enter_context(patch.object(unify_release, name))
                       for name in ('safe', 'preflight', 'prepare', 'apply')]
            with self.assertRaisesRegex(RuntimeError, 'Whole-site command is retired'):
                unify_release.main()
            for action in actions:
                action.assert_not_called()

    def test_legacy_worker_cli_refuses_without_dispatch(self):
        guards = self.guarded()
        path = REPO / 'scripts/release/image-inputs-worker.py'
        for mode in ('native-pause', 'api-pause', 'api-resume', 'api-verify'):
            with self.subTest(mode=mode), patch('sys.argv', [str(path), mode, '60']):
                with self.assertRaises(SystemExit) as refused:
                    runpy.run_path(str(path), run_name='__main__')
                self.assertIn('scripts/release/intranet/release.py', str(refused.exception))
                self.assertIn('--scope', str(refused.exception))
        for guard in guards:
            guard.assert_not_called()

    def test_imports_and_intranet_engine_remain_available_without_side_effects(self):
        guards = self.guarded()
        ssh = load(HERE / 'transport.py', 'retirement_transport')
        engine = load(REPO / 'scripts/release/intranet/engine.py', 'retirement_engine')
        self.assertTrue(callable(ssh.connect))
        for name in ('configure', 'prepare', 'apply', 'recover'):
            self.assertTrue(callable(getattr(engine, name)))
        for name in ('prepare', 'safe', 'digest', 'contexts', 'drain',
                     'app_command', 'start_apps', 'stop_apps', 'data_identity'):
            self.assertTrue(callable(getattr(engine.u, name)))
        for guard in guards:
            guard.assert_not_called()


if __name__ == '__main__':
    unittest.main()
