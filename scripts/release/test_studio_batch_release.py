"""Behavioral release boundaries; no production command is executed by these tests."""
import importlib.util
import copy
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


d, baseline = map(load, ('studio-batch-deploy', 'studio-batch-baseline'))
r = d.r


class StudioBatchReleaseTests(unittest.TestCase):
    def package(self, root, mode='release'):
        paths = {'api/'+n for n in r.FILES} | {'tests/'+n for n in ('conftest.py', *r.TESTS)} | {
            'frontend/package.json', 'frontend/dist/index.html', 'frontend/dist/assets/index-test.js'} | {
            'scripts/release/'+n+'.py' for n in r.HELPERS}
        for name in paths:
            path = root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"version":"0.2.64"}' if name.endswith('package.json') else 'content')
        (root/'frontend/dist/index.html').write_text('<script src="/assets/index-test.js"></script>')
        files = {n:r.digest(root/n) for n in paths}
        manifest = dict(release='studio-batch-test', version=r.VERSION, revision=r.REVISION, mode=mode,
            commit='a'*40, candidateId='b'*64, native={'units':{u:{'files':{n:'b'*64 for n in r.NATIVE_FILES}} for u in r.UNITS}},
            api={'image':r.BASE_IMAGE, 'files':{n:{'baseline':None, 'sha256':files['api/'+n]} for n in r.FILES}},
            files=files)
        manifest['frontendBuild'] = dict(commit=manifest['commit'],sourceTree='c'*40,lockSha256='d'*64,
            files={n:h for n,h in files.items() if n.startswith('frontend/dist/')})
        (root/'release.json').write_text(json.dumps(manifest))
        return manifest

    def test_scope_preserves_schema_native_and_existing_runtime(self):
        self.assertEqual(r.FILES, baseline.FILES)
        self.assertEqual(len(r.FILES), 5)
        self.assertEqual(r.NATIVE_FILES, {'app/overseas/studio/image_edits.py'})
        self.assertEqual((r.OLD_REVISION, r.REVISION), ('overseas_0026', 'overseas_0026'))
        self.assertIn('test_studio_image_references_validation.py', r.TESTS)
        self.assertNotIn('sku-database', r.HELPERS)
        self.assertEqual(load('sku-runtime').VERSION, '0.2.60')

    def test_incomplete_frontend_build_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Missing frontend entry'):
            r.verify_frontend('<script src="/assets/missing.js"></script>', {'frontend/dist/index.html'})
        with self.assertRaisesRegex(RuntimeError, 'must reference JavaScript'):
            r.verify_frontend('<html>build pending</html>', {'frontend/dist/index.html'})

    def test_package_rejects_drift_extra_api_native_and_legacy_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for corruption in ('revision', 'native', 'api', 'build', 'bytes'):
                manifest = self.package(root)
                self.assertEqual(r.verify_package(root), manifest)
                if corruption == 'revision':
                    manifest['revision'] = 'overseas_0025'
                elif corruption == 'native':
                    manifest['native']['units'][r.UNITS[0]]['files']['app/overseas/db.py'] = 'a'*64
                elif corruption == 'api':
                    manifest['api']['files']['app/overseas/main.py'] = {}
                elif corruption == 'build':
                    manifest['frontendBuild']['commit'] = 'f'*40
                else:
                    (root/'api/app/overseas/studio/image_edits.py').write_text('changed')
                (root/'release.json').write_text(json.dumps(manifest))
                with self.assertRaises(RuntimeError):
                    r.verify_package(root)

    def test_candidate_can_test_but_cannot_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.package(root, 'candidate')
            with patch.object(d.sku, 'state', return_value=({}, root)), patch.object(r, 'sql', return_value=r.REVISION), \
                 patch.object(r, 'run') as run:
                self.assertEqual(d.state(root), ({}, root))
                with self.assertRaisesRegex(RuntimeError, 'test-only'):
                    d.gate(root)
                run.assert_not_called()

    def test_prepare_retains_prior_secret_overlay_and_only_changes_image(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, work = root/'source', root/'work'
            work.mkdir()
            manifest = self.package(source)
            live = {'Id':'old', 'Image':r.BASE_IMAGE, 'State':{'Running':True},
                    'Config':{'Env':['OVERSEAS_DESIGN_API_KEY=synthetic-private-value']}}
            compose = {'paths':['/opt/base.yml', '/opt/previous/api-overlay.json'], 'files':{}}
            original = {'services':{'api':{'image':r.BASE_IMAGE,
                        'environment':{'OVERSEAS_DESIGN_API_KEY':'synthetic-private-value'}}, 'redis':{'image':'redis'}}}
            after = copy.deepcopy(original)
            after['services']['api']['image'] = 'new-image'
            def run(*args, **kwargs):
                return 'new-image' if args[:3] == ('docker', 'image', 'inspect') else ''
            with patch.object(r, 'inspect', return_value=live), \
                 patch.object(r, 'hashes', return_value={n:None for n in r.FILES}), \
                 patch.object(r.b, 'snapshot', return_value={'frontendVersion':r.BASE_VERSION}), \
                 patch.object(r, 'sql', return_value=r.REVISION), \
                 patch.object(r.a, 'compose_info', return_value=compose), \
                 patch.object(r.a, 'check_live_config'), patch.object(r, 'native_environment', return_value='envhash'), \
                 patch.object(r.a, 'compose', side_effect=[json.dumps(original), json.dumps(after)]), \
                 patch.object(r, 'helper', return_value=SimpleNamespace(preflight=Mock())), \
                 patch.object(r, 'run', side_effect=run), patch.object(r, 'unchanged'), patch.object(d, 'state'):
                d.prepare(work, source)
            saved = json.loads((work/'prepared.json').read_text())
            self.assertEqual(saved['compose']['paths'], compose['paths'])
            self.assertEqual(json.loads((work/'api-overlay.json').read_text()), {'services':{'api':{'image':'new-image'}}})
            self.assertNotIn('synthetic-private-value', (work/'prepared.json').read_text())
            dockerfile = (work/'api-build/Dockerfile').read_text()
            self.assertEqual(dockerfile.count('COPY '), 5)
            self.assertNotIn('RUN ', dockerfile)

    def test_import_preflight_failure_never_stops_api(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(d, 'state', return_value=({'oldId':'old', 'manifest':'m'}, root)), \
                 patch.object(r, 'inspect', return_value={'Id':'old'}), \
                 patch.object(r, 'worker', return_value={'node':'node'}), \
                 patch.object(r, 'sql', return_value='1'), patch.object(r, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'imports still active'):
                    d.gate(root)
                run.assert_not_called()
            self.assertFalse((root/'GATE_STARTED').exists())

    def test_import_race_aborts_before_pause_backup_or_switch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(d, 'state', return_value=({'oldId':'old', 'manifest':'m'}, root)), \
                 patch.object(r, 'inspect', side_effect=[{'Id':'old'}, {'State':{'Running':False}}]), \
                 patch.object(r, 'worker', return_value={'node':'node'}) as worker, \
                 patch.object(r, 'sql', side_effect=['0', '1']), patch.object(r, 'run') as run, \
                 patch.object(r, 'helper') as helper:
                with self.assertRaisesRegex(RuntimeError, 'imports still active'):
                    d.gate(root)
                run.assert_called_once_with('docker', 'stop', '--time', '-1', r.API, timeout=60)
                self.assertEqual(worker.call_args_list[0].args, ('idle',))
                self.assertEqual(worker.call_count, 1)
                helper.assert_not_called()
            self.assertTrue((root/'GATE_STARTED').exists())
            self.assertFalse((root/'gate.json').exists())

    def test_graceful_stop_timeout_never_pauses_or_force_kills(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(d, 'state', return_value=({'oldId':'old'}, root)), \
                 patch.object(r, 'inspect', return_value={'Id':'old'}), \
                 patch.object(r, 'worker', return_value={'node':'node'}) as worker, \
                 patch.object(r, 'sql', return_value='0'), \
                 patch.object(r, 'run', side_effect=subprocess.TimeoutExpired('docker', 60)) as run:
                with self.assertRaises(subprocess.TimeoutExpired):
                    d.gate(root)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(worker.call_count, 1)
            self.assertTrue((root/'GATE_STARTED').exists())

    def test_successful_gate_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            events = []
            def worker(mode):
                events.append(mode)
                return {'node':'node'}
            with patch.object(d, 'state', return_value=({'oldId':'old', 'manifest':'m'}, root)), \
                 patch.object(r, 'inspect', side_effect=[{'Id':'old'}, {'State':{'Running':False}}]), \
                 patch.object(r, 'worker', side_effect=worker), \
                 patch.object(d, 'imports_idle', side_effect=lambda: events.append('imports')), \
                 patch.object(r, 'run', side_effect=lambda *a, **k: events.append('stop')), \
                 patch.object(r, 'helper', return_value=SimpleNamespace(stop=lambda *a: events.append('native-stop'))):
                d.gate(root)
            self.assertEqual(events, ['idle', 'imports', 'stop', 'imports', 'idle', 'pause', 'native-stop'])

    def test_native_is_required_before_switch_and_gateway_refresh_follows(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            (work/'backup').mkdir()
            (work/'backup/overseas.dump').write_bytes(b'isolated dump')
            r.private(work/'backup/COMPLETE',{'manifest':'m','dumpSha256':r.digest(work/'backup/overseas.dump')})
            data = {'oldId':'old','manifest':'m','image':'new','compose':{'paths':['private-overlay']}}
            events = []
            native = SimpleNamespace(verified=lambda *a: events.append('native-verified'))
            gateway = SimpleNamespace(refresh=lambda *a: events.append('gateway-refreshed'))
            with patch.object(d,'state',return_value=(data,None)), \
                 patch.object(r,'inspect',return_value={'Id':'old','State':{'Running':False}}), \
                 patch.object(r,'helper',side_effect=[native,gateway]), \
                 patch.object(r.a,'compose',side_effect=lambda *a,**k:events.append('api')) as compose, \
                 patch.object(d,'verify',side_effect=lambda *a:events.append('verified')):
                d.api(work)
            self.assertEqual(events,['native-verified','api','gateway-refreshed','verified'])
            compose.assert_called_once_with(data['compose'],'up','-d','--no-deps','--no-build','api',
                                            overlay=work/'api-overlay.json')

    def test_installed_tests_run_candidate_image_with_isolated_pg_no_production_env(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            with patch.object(d.sku,'state',return_value=({'manifest':'abc','image':'candidate-sha'},work)), \
                 patch.object(r,'run',return_value='[{"Image":"postgres-image"}]') as run, \
                 patch.object(d.sku,'installed_pytest',return_value='30 passed') as pytest:
                d.sku.test(work)
            command = pytest.call_args.args[0]
            self.assertIn('/app/tests/test_studio_message_metadata_postgres.py',command)
            self.assertIn('candidate-sha',command)
            self.assertIn('container:hx-sku-tests-abc',command)
            self.assertIn('--read-only',command)
            self.assertNotIn('--env-file',command)
            self.assertEqual(run.call_args.args,('docker','rm','-f','-v','hx-sku-tests-abc'))

    def test_static_adapter_keeps_original_runtime_separate(self):
        frontend = r.helper('sku-frontend')
        self.assertEqual(frontend.BASE_VERSION,'0.2.63')
        self.assertEqual(frontend.r.VERSION,'0.2.64')
        self.assertEqual(load('sku-frontend').BASE_VERSION,'0.2.59')


if __name__ == '__main__':
    unittest.main()
