"""Pure argv validation plus isolated filesystem deployment tests; never start Codex."""
import ast
from contextlib import ExitStack
import os
from pathlib import Path
import socket
import tempfile
import types
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

import build_sandbox_proxy as b


def original_workspace():
    # This one-time patch targets the pre-migration release, not today's workspace.
    source = Path(__file__).with_name('fixtures') / 'workspace_before_lan_proxy.py.fixture'
    content = source.read_bytes().replace(b'\r\n', b'\n')
    if b.digest(content) != '35d4ba0240f5c1ffaaec317c3592ef28899cf04c414f6f640b737ef3465fcb75':
        raise RuntimeError('historical workspace fixture drift')
    return content


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.original = original_workspace()
        self.patched = b.patched_source(self.original, b.digest(self.original))

    def sandbox(self, environment, content=None):
        tree = ast.parse((content or self.patched).decode())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'sandbox_command')
        module = ast.Module(body=[function], type_ignores=[])
        globals_ = {'os': types.SimpleNamespace(name='posix', environ=environment), 'Path': Path, 'urlsplit': urlsplit}
        exec(compile(module, 'workspace-sandbox-test.py', 'exec'), globals_)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary, helper, bwrap = root / 'codex', root / 'codex-code-mode-host', root / 'bwrap'
            for path in (binary, helper, bwrap):
                path.write_text('synthetic only; never executed')
            workspace = types.SimpleNamespace(home=root, work=root, control=root, local_skill=None,
                                              skill_name='skill', use_skill=False, persistent=False)
            return globals_['sandbox_command'](workspace, binary, ['exec', '--sandbox', 'workspace-write'], str(bwrap))

    def test_production_default_and_invalid_flags_remain_denied(self):
        for flag in (None, '', '0', 'true', '2'):
            env = {'APP_ENV': 'production', b.PROXY: 'http://127.0.0.1:7890'}
            if flag is not None:
                env[b.FLAG] = flag
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.sandbox(env)
        self.assertNotIn('HTTP_PROXY', self.sandbox({'APP_ENV': 'production'}))

    def test_explicit_production_opt_in_preserves_only_loopback_proxy(self):
        for proxy in ('http://127.0.0.1:7890', 'http://localhost:7890/', 'https://[::1]:7890'):
            argv = self.sandbox({'APP_ENV': 'production', b.FLAG: '1', b.PROXY: proxy})
            for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
                self.assertEqual(argv[argv.index(key) + 1], proxy)
            self.assertEqual(argv[argv.index('NO_PROXY') + 1], 'localhost,127.0.0.1,::1')
            self.assertIn('--clearenv', argv)
            for unchanged in ('--unshare-user', '--unshare-pid', '--unshare-ipc', '--unshare-uts', 'workspace-write'):
                self.assertIn(unchanged, argv)
            self.assertNotIn('--unshare-net', argv)
        # Overseas process can omit generic APP_ENV; the explicit flag is still required.
        self.assertIn('HTTP_PROXY', self.sandbox({b.FLAG: '1', b.PROXY: 'http://localhost:7890'}))

    def test_remote_credentials_schemes_paths_ports_and_controls_rejected(self):
        proxies = ['http://192.168.1.245:7890', 'http://example.com:7890', 'http://127.0.0.2:7890',
                   'http://localhost.evil:7890', 'http://user@localhost:7890', 'http://:pw@localhost:7890',
                   'socks5://localhost:7890', 'ftp://localhost:7890', 'http://localhost',
                   'http://localhost:0', 'http://localhost:65536', 'http://localhost:bad',
                   'http://localhost:7890/path', 'http://localhost:7890?x=1', 'http://localhost:7890#x',
                   ' http://localhost:7890', 'http://localhost:7890\t', '\nhttp://localhost:7890',
                   '\x01http://localhost:7890', '\x00http://localhost:7890', 'http://localhost:7890\x7f']
        for proxy in proxies:
            with self.subTest(proxy=proxy), self.assertRaises(ValueError):
                self.sandbox({'APP_ENV': 'production', b.FLAG: '1', b.PROXY: proxy})

    def test_existing_development_test_behavior_and_source_drift(self):
        for app_env in ('development', 'test'):
            self.assertIn('HTTP_PROXY', self.sandbox({'APP_ENV': app_env, b.PROXY: 'http://localhost:7890'}))
        with self.assertRaises(ValueError):
            self.sandbox({'APP_ENV': 'production', b.FLAG: '1', b.PROXY: 'http://localhost:7890'}, self.original)
        for content in (self.original + b'\n', self.patched):
            with self.assertRaises(ValueError):
                b.patched_source(content, b.digest(self.original))
        self.assertEqual(self.patched.decode().count(b.NEW_GATE), 1)
        restored = self.patched.decode().replace(b.NEW_GATE, b.OLD_GATE).replace(b.NEW_CONTROL, b.OLD_CONTROL)
        self.assertEqual(restored, self.original.decode())

    def test_environment_preserves_app_env_and_secrets(self):
        original = b'APP_ENV="production"\nNEW_SECRET="private-$x-%H"\n'
        actual = b.patched_env(original)
        self.assertTrue(actual.startswith(original))
        self.assertEqual(actual.count(b'APP_ENV='), 1)
        self.assertIn((b.FLAG + '="1"\n').encode(), actual)
        self.assertIn((b.PROXY + '="http://127.0.0.1:7890"\n').encode(), actual)
        with self.assertRaises(ValueError):
            b.patched_env(actual)

    def layout(self, tmp, stack, with_env=True):
        root = Path(tmp).resolve()
        targets = (root / 'domestic.py', root / 'overseas.py')
        envs = (root / 'domestic.env', root / 'overseas.env')
        for name, value in {'PRIVATE': root, 'CANDIDATE': root / 'candidate', 'PLAN': root / 'plan.json',
                            'TARGETS': targets, 'ENV_FILES': envs}.items():
            stack.enter_context(patch.object(b, name, value))
        for target in targets:
            target.write_bytes(self.original)
        if with_env:
            for env in envs:
                env.write_bytes(b'APP_ENV="production"\nSECRET="private"\n')
                env.chmod(0o600)
        data = {'native_hashes': {str(p): {'sha256': b.digest(self.original)} for p in targets}}
        return targets, envs, data

    @unittest.skipUnless(os.name == 'posix', 'requires Unix file modes')
    def test_atomic_apply_backups_and_repeated_run_refused(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            targets, envs, data = self.layout(tmp, stack)
            self.assertTrue(b.prepare(data).startswith('applied:'))
            for i, target in enumerate(targets):
                self.assertEqual(target.read_bytes(), self.patched)
                self.assertEqual((b.CANDIDATE / (str(i) + '.source')).read_bytes(), self.original)
            self.assertNotIn('private', (b.CANDIDATE / 'manifest.json').read_text())
            self.assertTrue(all((b.CANDIDATE / (str(i) + '.applied')).exists() for i in range(4)))
            self.assertTrue(all(p.stat().st_mode & 0o077 == 0 for p in envs))
            with self.assertRaises(FileExistsError):
                b.prepare(data)

    def test_missing_environment_is_plan_only_and_drift_refused(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            targets, _, data = self.layout(tmp, stack, with_env=False)
            self.assertTrue(b.prepare(data).startswith('plan-only:'))
            self.assertTrue(b.PLAN.exists())
            self.assertFalse(b.CANDIDATE.exists())
            self.assertTrue(all(p.read_bytes() == self.original for p in targets))
            targets[0].write_bytes(self.original + b'# drift')
            with self.assertRaises(ValueError):
                b.prepare(data)
            self.assertFalse(b.CANDIDATE.exists())

    @unittest.skipUnless(os.name == 'posix', 'requires Unix symlinks')
    def test_symlink_and_shared_environment_rejected_without_changes(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            targets, envs, data = self.layout(tmp, stack)
            envs[0].chmod(0o644)
            with self.assertRaises(ValueError):
                b.prepare(data)
            self.assertFalse(b.CANDIDATE.exists())
            envs[0].chmod(0o600)
            envs[0].unlink()
            envs[0].symlink_to(envs[1])
            with self.assertRaises(ValueError):
                b.prepare(data)
            self.assertTrue(all(p.read_bytes() == self.original for p in targets))

    def test_source_host_guard_before_reads(self):
        with patch.object(socket, 'gethostname', return_value='racknerd-058889d'), patch.object(Path, 'read_text') as read:
            with self.assertRaises(RuntimeError):
                b.main()
            read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
