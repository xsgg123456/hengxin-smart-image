"""Synthetic native deployment tests; no real services, credentials or production files."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import build_native as b


def fixtures():
    units, config, env = [], {}, {}
    for name in sorted(b.UNITS):
        root = ('/opt/hengxin-overseas-releases/overseas-20261024-b6289eb/backend'
                if 'overseas' in name else '/opt/hengxin-native-releases/domestic-record-filters-20261022-2f08f8f/backend')
        path = '/etc/systemd/system/' + name + '.service'
        overlay = path + '.d/50-resources.conf'
        argv = [root + '/.venv/bin/python', '-m', 'app.example']
        if name.endswith('worker'):
            argv += ['--hostname=worker@racknerd-058889d', '--literal=$HOME/%H', 'space and "quote"', 'line\nsecond']
        if name == 'hengxin-codex-auth':
            argv += ['--allowed-uid', '1001', '--allowed-uid', '999']
        units.append({'name': name, 'cwd': root, 'argv': argv,
                      'properties': {'FragmentPath': path, 'DropInPaths': overlay}})
        config[path] = '''[Unit]
Description=Synthetic source
After=source-dependency.service
[Service]
User=codex
Group=hengxin-codex-auth
Environment="OLD_SECRET=must-disappear" \\
 # ignored inside continuation
 "OLD_OTHER=also-disappear"
EnvironmentFile=/old/production.env
WorkingDirectory=/old/code
ExecStart=/old/code/python --old
RuntimeDirectory=hengxin-example
RuntimeDirectoryMode=0750
RuntimeDirectoryPreserve=yes
UMask=0077
NoNewPrivileges=yes
Restart=on-failure
RestartSec=5
MemoryMax=6G
SupplementaryGroups=first-group
[Install]
WantedBy=multi-user.target
'''
        config[overlay] = '''[Service]
MemoryMax=2G
CPUQuota=200%
TasksMax=512
SupplementaryGroups=
SupplementaryGroups=hengxin-codex-auth
ExecStart=
ExecStart=/another/old/python
EnvironmentFile=/another/old.env
'''
        env[name] = {'NEW_SECRET': 'secret-$literal-%H', 'WORKER_NODE_NAME': 'node@racknerd-058889d'}
    original = ("# synthetic account source\nimport os\n"
                "def main(args, managers):\n    return " + b.OLD_CALL + '\n').encode()
    return {'units': units, 'config_files': config,
            'native_hashes': {str(b.ACCOUNT): {'sha256': b.digest(original)}}}, env, original


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.data, self.env, self.original = fixtures()

    def test_envfile_exact_escaping_and_multiline(self):
        self.assertEqual(b.env_text({'X': ' $HOME ${X} %H "quote" \\ `cmd` \nend '}),
                         'X=" \\$HOME \\${X} %H \\"quote\\" \\\\ \\`cmd\\` \nend "\n')
        self.assertEqual(b.env_text({'EMPTY': '', 'UNICODE': '中文'}), 'EMPTY=""\nUNICODE="中文"\n')
        for env in ({'BAD=KEY': 'x'}, {'OK': 'x\0y'}, {'OK': None}):
            with self.assertRaises(ValueError):
                b.env_text(env)

    def test_argv_exact_percent_dollar_backslash_quotes(self):
        self.assertEqual(b.unit_quote('$HOME/%H a"b\\c\n\t', True), '"$$HOME/%%H a\\"b\\\\c\\n\\t"')
        self.assertEqual(b.unit_quote('/path/%literal'), '"/path/%%literal"')
        self.assertEqual(b.unit_quote('', True), '""')
        with self.assertRaises(ValueError):
            b.unit_quote('bad\0argument', True)

    def test_path_directives_have_no_quotes_and_escape_specifiers(self):
        self.assertEqual(b.unit_path('/etc/hengxin-lan/service.env'), '/etc/hengxin-lan/service.env')
        self.assertEqual(b.unit_path('/opt/100%/literal%H'), '/opt/100%%/literal%%H')
        for value in ('relative', '//root', '/opt/../etc', '/opt/./path', '/opt//path',
                      '/opt/a b', '/opt/a\tb', '/opt/a\nb', '/opt/a\0b', '/opt/a\x7fb',
                      '/opt/"quoted"', "/opt/'quoted'", '/opt/back\\slash'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                b.unit_path(value)

    @unittest.skipUnless(shutil.which('systemd-analyze'), 'requires Linux systemd-analyze')
    def test_real_systemd_parser_accepts_units_and_rejects_quoted_path_regression(self):
        for unit in self.data['units']:
            unit['argv'][0] = '/usr/bin/python3'
        outputs, _ = b.build(self.data, self.env)
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name, content in outputs.items():
                if name.endswith('.service'):
                    path = Path(tmp) / name
                    path.write_bytes(content)
                    paths.append(str(path))
            result = subprocess.run(['systemd-analyze', 'verify', '--man=no', *paths],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            broken = Path(tmp) / 'regression.service'
            text = outputs['hengxin-codex-accounts.service'].decode()
            text = '\n'.join('WorkingDirectory="' + line.split('=', 1)[1] + '"'
                             if line.startswith('WorkingDirectory=') else line for line in text.splitlines())
            broken.write_text(text)
            rejected = subprocess.run(['systemd-analyze', 'verify', '--man=no', str(broken)],
                                      capture_output=True, text=True, timeout=30)
            self.assertNotEqual(rejected.returncode, 0)

    def test_unit_resources_order_and_runtime_configuration_preserved(self):
        outputs, manifest = b.build(self.data, self.env)
        self.assertEqual(len(outputs), 14)
        self.assertEqual(len(manifest['units']), 7)
        for name in b.UNITS:
            text = outputs[name + '.service'].decode()
            for expected in ('UMask=0077', 'NoNewPrivileges=yes', 'RuntimeDirectory=hengxin-example',
                             'RuntimeDirectoryMode=0750', 'RuntimeDirectoryPreserve=yes', 'Restart=on-failure',
                             'RestartSec=5', 'MemoryMax=2G', 'CPUQuota=200%', 'TasksMax=512',
                             'After=network-online.target docker.service mihomo.service'):
                self.assertIn(expected, text)
            self.assertLess(text.index('MemoryMax=6G'), text.index('MemoryMax=2G'))
            self.assertIn('SupplementaryGroups=\nSupplementaryGroups=hengxin-codex-auth', text)
            for forbidden in ('/old/', 'must-disappear', 'also-disappear', 'Environment=', 'racknerd-058889d'):
                self.assertNotIn(forbidden, text)
            self.assertEqual(text.count('ExecStart='), 1)
            self.assertEqual(text.count('WorkingDirectory='), 1)
            self.assertIn('EnvironmentFile=/etc/hengxin-lan/' + name + '.env\n', text)
            unit = next(u for u in self.data['units'] if u['name'] == name)
            self.assertIn('WorkingDirectory=' + unit['cwd'] + '\n', text)
            self.assertNotIn('WorkingDirectory="', text)
            self.assertNotIn('EnvironmentFile="', text)
        for name in ('hengxin-vps-codex-worker', 'hengxin-overseas-worker'):
            text = outputs[name + '.service'].decode()
            self.assertIn('mihomo.service hengxin-codex-accounts.service', text)
            self.assertIn('"--hostname=worker@hengxin-ai-245"', text)
            self.assertIn('"--literal=$$HOME/%%H"', text)
            self.assertNotIn('ExecStartPre=', text)
        self.assertNotIn('secret-$literal', json.dumps(manifest))

    def test_uid_adaptation_and_wrong_values_rejected(self):
        outputs, _ = b.build(self.data, self.env)
        legacy = outputs['hengxin-codex-auth.service'].decode()
        self.assertIn('"--allowed-uid" "1002"', legacy)
        self.assertNotIn('"999"', legacy)
        account = outputs['hengxin-codex-accounts.env'].decode()
        self.assertIn('HX_OVERSEAS_WORKER_UID="1002"', account)
        self.env['hengxin-codex-accounts']['HX_OVERSEAS_WORKER_UID'] = '999'
        with self.assertRaises(ValueError):
            b.build(self.data, self.env)
        self.env['hengxin-codex-accounts']['HX_OVERSEAS_WORKER_UID'] = '1002'
        next(u for u in self.data['units'] if u['name'] == 'hengxin-codex-auth')['argv'][-1] = '998'
        with self.assertRaises(ValueError):
            b.build(self.data, self.env)

    def test_patch_hash_drift_anchor_default_and_syntax(self):
        patched, delta = b.patch_plan(self.data, self.original)
        self.assertIn(b.NEW_CALL.encode(), patched)
        self.assertIn(b"os.environ.get('HX_OVERSEAS_WORKER_UID', '999')", patched)
        self.assertEqual(delta['source_sha256'], hashlib.sha256(self.original).hexdigest())
        compile(patched, 'test-patch.py', 'exec')
        for content in (self.original + b'\n', patched):
            with self.assertRaises(ValueError):
                b.patch_plan(self.data, content)
        doubled = self.original + b'\n# ' + b.OLD_CALL.encode()
        self.data['native_hashes'][str(b.ACCOUNT)]['sha256'] = b.digest(doubled)
        with self.assertRaises(ValueError):
            b.patch_plan(self.data, doubled)

    def temporary_layout(self, directory, stack):
        base = Path(directory).resolve()
        account, systemd, root = base / 'service.py', base / 'systemd', base / 'candidate'
        account.write_bytes(self.original)
        systemd.mkdir()
        stack.enter_context(patch.object(b, 'ACCOUNT', account))
        stack.enter_context(patch.object(b, 'ROOT', root))
        stack.enter_context(patch.object(b, 'SYSTEMD', systemd))
        data, env, _ = fixtures()
        return account, root, systemd, data, env

    def test_candidates_exclusive_patch_backup_and_second_run_refused(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            account, root, systemd, data, env = self.temporary_layout(tmp, stack)
            b.install_candidate(data, env)
            self.assertEqual((root / 'account-service.source.py').read_bytes(), self.original)
            self.assertEqual(account.read_bytes(), (root / 'account-service.patched.py').read_bytes())
            self.assertEqual(list(systemd.iterdir()), [])
            self.assertEqual(len(list(root.iterdir())), 17)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            with self.assertRaises(FileExistsError):
                b.install_candidate(data, env)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})

    def test_preflight_drift_and_existing_final_unit_cause_no_writes(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            account, root, systemd, data, env = self.temporary_layout(tmp, stack)
            account.write_bytes(self.original + b'# drift')
            with self.assertRaises(ValueError):
                b.install_candidate(data, env)
            self.assertFalse(root.exists())
            self.assertTrue(account.read_bytes().endswith(b'# drift'))
            account.write_bytes(self.original)
            (systemd / 'hengxin-codex-accounts.service').write_text('existing')
            with self.assertRaises(FileExistsError):
                b.install_candidate(data, env)
            self.assertFalse(root.exists())
            self.assertEqual(account.read_bytes(), self.original)

    def test_bad_paths_command_directives_and_inventory_fail_closed(self):
        with self.assertRaises(ValueError):
            b.safe_path(Path('relative'))
        with tempfile.TemporaryDirectory() as tmp, patch.object(b.Path, 'is_symlink', return_value=True):
            with self.assertRaises(ValueError):
                b.safe_path(Path(tmp).absolute())
        with self.assertRaises(ValueError):
            b.preserved('[Service]\nExecStartPre=/bin/unsafe\n')
        with self.assertRaises(ValueError):
            b.preserved('[Service]\nEnvironment=abc\\')
        self.data['units'][0]['cwd'] = '/unexpected'
        with self.assertRaises(ValueError):
            b.build(self.data, self.env)
        self.data['units'].pop()
        with self.assertRaises(ValueError):
            b.build(self.data, self.env)

    def test_host_guard_before_reads(self):
        with patch.object(b.socket, 'gethostname', return_value='racknerd-058889d'), patch.object(b.Path, 'read_text') as read:
            with self.assertRaises(RuntimeError):
                b.main()
            read.assert_not_called()

    def test_real_account_id_mismatch_refused_before_reads(self):
        import types
        users = types.SimpleNamespace(getpwnam=lambda name: types.SimpleNamespace(pw_uid=999))
        groups = types.SimpleNamespace(getgrnam=lambda name: types.SimpleNamespace(gr_gid=986))
        with patch.object(b.socket, 'gethostname', return_value='hengxin-ai-245'), \
                patch.object(b.os, 'geteuid', return_value=0, create=True), \
                patch.dict('sys.modules', {'pwd': users, 'grp': groups}), \
                patch.object(b.Path, 'read_text') as read:
            with self.assertRaises(RuntimeError):
                b.main()
            read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
