"""Production mutations mocked: gate order, fault recovery and immutable boundaries."""
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-','_'),Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


d = load('sku-deploy')
r = load('sku-runtime')
f = load('sku-frontend')
db = load('sku-database')


class ReleaseTests(unittest.TestCase):
    def test_failed_installed_pytest_preserves_both_streams(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = subprocess.CompletedProcess(['pytest'],1,'1 failed: assertion details','fixture stderr')
            with patch.object(d.subprocess,'run',return_value=result) as run:
                with self.assertRaisesRegex(RuntimeError,'installed-tests.txt'):
                    d.installed_pytest(['pytest'],root)
            run.assert_called_once_with(['pytest'],capture_output=True,text=True,timeout=600)
            saved = (root/'installed-tests.txt').read_text()
            self.assertIn('assertion details',saved)
            self.assertIn('fixture stderr',saved)
            self.assertFalse((root/'INSTALL_TESTS_PASSED').exists())

    def test_timed_out_installed_pytest_preserves_partial_streams(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            error = subprocess.TimeoutExpired(['pytest'],600,output=b'partial test output',stderr=b'partial stderr')
            with patch.object(d.subprocess,'run',side_effect=error):
                with self.assertRaises(subprocess.TimeoutExpired):
                    d.installed_pytest(['pytest'],root)
            saved = (root/'installed-tests.txt').read_text()
            self.assertIn('partial test output',saved)
            self.assertIn('partial stderr',saved)
            self.assertIn('INSTALL_TEST_TIMEOUT',saved)

    def test_skipped_installed_pytest_is_saved_and_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = subprocess.CompletedProcess(['pytest'],0,'1 passed, 1 skipped','')
            with patch.object(d.subprocess,'run',return_value=result):
                with self.assertRaisesRegex(RuntimeError,'incomplete'):
                    d.installed_pytest(['pytest'],root)
            self.assertIn('1 skipped',(root/'installed-tests.txt').read_text())

    def test_native_scope_excludes_every_api_draft_dependency(self):
        self.assertEqual(r.NATIVE_FILES, {'app/overseas/db.py'})
        self.assertIn('app/overseas/main.py',r.FILES)
        self.assertNotIn('app/main.py',r.FILES)
        self.assertIn('migrations/overseas/versions/0026_requirement_drafts.py',r.FILES)
        self.assertEqual((r.OLD_REVISION,r.REVISION), ('overseas_0025','overseas_0026'))

    def gate_fixture(self,root,busy_on=None):
        events = []
        def worker(mode,*args):
            events.append(mode)
            if busy_on == events.count('idle') and mode == 'idle':
                raise RuntimeError('pending jobs')
            return {'node':'existing-node'}
        def run(*args,**kwargs):
            events.append(args[1])
            self.assertEqual(args,('docker','stop','--time','-1',r.API))
            self.assertEqual(kwargs['timeout'],60)
        return events,worker,run

    def test_gate_checks_idle_and_pauses_before_graceful_native_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            events,worker,run = self.gate_fixture(root)
            with patch.object(d,'state',return_value=({'oldId':'old','manifest':'m','workflow':{'memberIds':[]}},None)), \
                 patch.object(d.r,'inspect',side_effect=[{'Id':'old'},{'State':{'Running':False}}]), \
                 patch.object(d.r,'worker',side_effect=worker),patch.object(d.r,'run',side_effect=run), \
                 patch.object(d.r,'helper') as helper:
                d.gate(root)
                helper.return_value.stop.assert_called_once()
            self.assertEqual(events,['idle','stop','idle','pause'])
            self.assertEqual(json.loads((root/'gate.json').read_text())['node'],'existing-node')

    def test_busy_preflight_does_not_stop_api(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            events,worker,run = self.gate_fixture(root,busy_on=1)
            with patch.object(d,'state',return_value=({'oldId':'old','manifest':'m','workflow':{'memberIds':[]}},None)), \
                 patch.object(d.r,'inspect',return_value={'Id':'old'}), \
                 patch.object(d.r,'worker',side_effect=worker),patch.object(d.r,'run',side_effect=run), \
                 patch.object(d.r,'helper'):
                with self.assertRaisesRegex(RuntimeError,'pending'):
                    d.gate(root)
            self.assertEqual(events,['idle'])
            self.assertFalse((root/'GATE_STARTED').exists())

    def test_raced_submit_leaves_consumer_running_and_records_recovery_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            events,worker,run = self.gate_fixture(root,busy_on=2)
            with patch.object(d,'state',return_value=({'oldId':'old','manifest':'m','workflow':{'memberIds':[]}},None)), \
                 patch.object(d.r,'inspect',side_effect=[{'Id':'old'},{'State':{'Running':False}}]), \
                 patch.object(d.r,'worker',side_effect=worker),patch.object(d.r,'run',side_effect=run), \
                 patch.object(d.r,'helper'):
                with self.assertRaisesRegex(RuntimeError,'pending'):
                    d.gate(root)
            self.assertEqual(events,['idle','stop','idle'])
            self.assertTrue((root/'GATE_STARTED').is_file())
            self.assertFalse((root/'gate.json').exists())

    def test_no_old_api_recovery_after_switch_started(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'API_SWITCH_STARTED').write_text('started')
            with patch.object(d,'state',return_value=({},None)),patch.object(d.r,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'forward recovery'):
                    d.recover_before_switch(root)
                run.assert_not_called()

    def frontend_fixture(self,root):
        source,app,backup = root/'source',root/'app',root/'backup'
        for base in (source,app):
            (base/'frontend/dist/assets').mkdir(parents=True)
        (app/'frontend/dist/index.html').write_text('old')
        (app/'frontend/dist/assets/old.js').write_text('old code')
        (app/'frontend/package.json').write_text('{"version":"0.2.59"}')
        (source/'frontend/dist/index.html').write_text('new')
        (source/'frontend/dist/assets/new.js').write_text('new code')
        (source/'frontend/package.json').write_text('{"version":"0.2.60"}')
        manifest = {'files':{p.relative_to(source).as_posix():r.digest(p) for p in source.rglob('*') if p.is_file()}}
        (source/'release.json').write_text(json.dumps(manifest))
        return source,app,backup,manifest

    def test_frontend_rollback_retains_both_asset_generations(self):
        with tempfile.TemporaryDirectory() as folder:
            source,app,backup,manifest = self.frontend_fixture(Path(folder))
            with patch.object(f.r,'verify_package',return_value=manifest):
                self.assertEqual(f.deploy(source,app,backup),'FRONTEND_0.2.60_INSTALLED')
            f.rollback(app,backup)
            self.assertEqual((app/'frontend/dist/index.html').read_text(),'old')
            self.assertTrue((app/'frontend/dist/assets/new.js').exists())
            self.assertTrue((app/'frontend/dist/assets/old.js').exists())

    def test_shared_asset_collision_aborts_before_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            source,app,backup,manifest = self.frontend_fixture(Path(folder))
            (app/'frontend/dist/assets/new.js').write_text('different')
            with patch.object(f.r,'verify_package',return_value=manifest),self.assertRaisesRegex(RuntimeError,'collision'):
                f.deploy(source,app,backup)
            self.assertFalse(backup.exists())
            self.assertEqual((app/'frontend/dist/index.html').read_text(),'old')

    def test_frontend_rollback_refuses_later_release(self):
        with tempfile.TemporaryDirectory() as folder:
            source,app,backup,manifest = self.frontend_fixture(Path(folder))
            with patch.object(f.r,'verify_package',return_value=manifest):
                f.deploy(source,app,backup)
            (app/'frontend/dist/index.html').write_text('third-release')
            with self.assertRaisesRegex(RuntimeError,'changed since deployment'):
                f.rollback(app,backup)


if __name__ == '__main__':
    unittest.main()
