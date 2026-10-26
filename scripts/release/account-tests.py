"""Release safeguards: exact production patch, API isolation and retained static rollback."""
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-','_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p, f, d = load('account-package'), load('account-frontend'), load('account-deploy')


class ReleaseTests(unittest.TestCase):
    def test_patch_preserves_production_only_code(self):
        raw = {'app/main.py':b'production_only = 42\n', 'app/overseas/main.py':b'production_overseas = 43\n',
               'app/core/config.py':b"class Settings:\n    codex_auth_broker_socket: str = ''\n    sentinel = 99\n"}
        result = p.patch_sources({n:base64.b64encode(v).decode() for n,v in raw.items()})
        self.assertTrue(result['app/main.py'].startswith(raw['app/main.py']))
        self.assertTrue(result['app/overseas/main.py'].startswith(raw['app/overseas/main.py']))
        self.assertEqual(result['app/core/config.py'].replace(b"    codex_account_management_socket: str = ''\n",b''),raw['app/core/config.py'])
        with self.assertRaises(AssertionError):
            p.patch_sources({n:base64.b64encode(v).decode() for n,v in result.items()})

    def test_no_private_root_in_api_overlay(self):
        text = Path(d.__file__).read_text(encoding='utf-8-sig')
        self.assertIn("'source': str(r.RUNTIME / domain)",text)
        self.assertNotIn("'source': str(r.PRIVATE)",text)
        self.assertIn("'--no-deps', '--no-build', 'api'",text)

    def test_frontend_backup_and_rollback_keep_both_generations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, app, backup = root/'source', root/'app', root/'backup'
            for folder in (source/'frontend/dist/assets',app/'frontend/dist/assets'):
                folder.mkdir(parents=True)
            (app/'frontend/dist/index.html').write_text('old')
            (app/'frontend/dist/assets/old-hash.js').write_text('old code')
            (app/'frontend/package.json').write_text('{"version":"0.2.53"}')
            (source/'frontend/dist/index.html').write_text('new')
            (source/'frontend/dist/assets/new-hash.js').write_text('new code')
            (source/'frontend/package.json').write_text('{"version":"0.2.54"}')
            files = {x.relative_to(source).as_posix():f.r.digest(x) for x in source.rglob('*') if x.is_file()}
            manifest = {'files':files,'frontendVersion':'0.2.54'}
            (source/'release.json').write_text(json.dumps(manifest))
            with patch.object(f.r,'verify_package',return_value=manifest):
                f.deploy(source,app,backup)
            self.assertEqual((app/'frontend/dist/index.html').read_text(),'new')
            f.rollback(app,backup)
            self.assertEqual((app/'frontend/dist/index.html').read_text(),'old')
            self.assertTrue((app/'frontend/dist/assets/old-hash.js').exists())
            self.assertTrue((app/'frontend/dist/assets/new-hash.js').exists())
            self.assertFalse((app/'FRONTEND_RELEASE.json').exists())

    def test_frontend_rejects_shared_asset_collision_before_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, app, backup = root/'source', root/'app', root/'backup'
            for folder in (source/'frontend/dist',app/'frontend/dist'):
                folder.mkdir(parents=True)
            (app/'frontend/package.json').write_text('{"version":"0.2.53"}')
            (app/'frontend/dist/shared.js').write_text('old')
            (source/'frontend/dist/shared.js').write_text('changed')
            with patch.object(f.r,'verify_package',return_value={}):
                with self.assertRaisesRegex(RuntimeError,'collision'):
                    f.deploy(source,app,backup)
            self.assertFalse(backup.exists())

    def test_worker_rollback_refuses_after_account_change(self):
        saved = {'workers':{'domestic':{'cwd':'/installed'}}, 'host':'/host',
                 'apis':{b:{'oldImage':'old'} for b in d.r.DOMAINS}}
        with tempfile.TemporaryDirectory() as directory:
            override = Path(directory)/'override'
            override.write_text('[Service]\nEnvironment=CODEX_AUTH_BROKER_SOCKET=' + str(d.r.RUNTIME/'worker.sock') + '\n')
            with patch.object(d,'validated',return_value=(saved,Path('/source'))), \
                 patch.object(d.r,'worker',return_value={'cwd':'/installed','pid':1}), \
                 patch.object(d.r,'drop_path',return_value=override), \
                 patch.object(d.r,'inspect',return_value={'Image':'old'}), \
                 patch.object(d,'control_status',return_value=1), \
                 patch.object(d.r,'worker_probe') as drain:
                with self.assertRaisesRegex(RuntimeError,'rollback unsafe'):
                    d.switch_worker(Path(directory),'domestic',rollback=True)
                drain.assert_not_called()
                self.assertTrue(override.exists())


if __name__ == '__main__':
    unittest.main()
