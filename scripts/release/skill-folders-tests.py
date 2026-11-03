"""Release boundary regression tests; all host operations are mocked."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('folders_deploy',Path(__file__).with_name('skill-folders-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
r = d.r

class ReleaseTests(unittest.TestCase):
    def package(self,root,mode='release'):
        paths = {'api/'+n for n in r.FILES}|{'tests/'+n for n in ('conftest.py',*r.TESTS)}|{
            'frontend/package.json','frontend/dist/index.html','frontend/dist/assets/test.js'}|{
            'scripts/release/'+n+'.py' for n in r.HELPERS}
        for name in paths:
            path = root/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('{"version":"0.2.63"}' if name.endswith('package.json') else 'content')
        (root/'frontend/dist/index.html').write_text('<script src="/assets/test.js"></script>')
        files = {n:r.digest(root/n) for n in paths}
        manifest = dict(release='skill-folders-test',version=r.VERSION,revision=r.REVISION,mode=mode,
            commit='a'*40,candidateId='b'*64,native={'units':{u:{'files':{n:'c'*64 for n in r.NATIVE_FILES}} for u in r.UNITS}},
            api={'image':r.BASE_IMAGE,'files':{n:dict(baseline=None,sha256=files['api/'+n]) for n in r.FILES}},files=files)
        (root/'release.json').write_text(json.dumps(manifest))
        return manifest

    def test_candidate_cannot_close_production_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.package(root,'candidate')
            with patch.object(d.sku,'state',return_value=({},root)),patch.object(r,'sql',return_value=r.REVISION),\
                    patch.object(r,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'Candidate'):
                    d.gate(root)
                run.assert_not_called()

    def test_fixed_scope_rejects_unreviewed_bytes_or_native_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.package(root)
            self.assertEqual(r.verify_package(root),manifest)
            manifest['native']['units'][r.UNITS[0]]['files']['app/overseas/db.py']='c'*64
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'native baseline scope'):
                r.verify_package(root)
            manifest = self.package(root)
            del manifest['native']['units'][r.UNITS[0]]['files']['app/overseas/management/installed_tree.py']
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'native baseline scope'):
                r.verify_package(root)
            manifest = self.package(root)
            del manifest['api']['files']['app/overseas/management/installed_tree.py']
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'Unexpected folder release scope'):
                r.verify_package(root)
            self.package(root)
            (root/'api/app/overseas/management/router.py').write_text('changed')
            with self.assertRaisesRegex(RuntimeError,'checksum mismatch'):
                r.verify_package(root)

    def test_publisher_only_has_database_identity_and_socket_access(self):
        before = {'services':{'api':{'image':'old','environment':{'OVERSEAS_DATABASE_URL':'synthetic-db',
            'OVERSEAS_APP_ENV':'production','OVERSEAS_LOCAL_SKILL_ROOT':d.p.SKILL_ROOT,
            'OVERSEAS_MINIO_SECRET_KEY':'must-not-copy','OVERSEAS_DESIGN_API_KEY':'must-not-copy',
            'OVERSEAS_IDENTITY_SERVICE_KEY':'must-not-copy','OVERSEAS_SKILL_TOGGLE_OWNER_ID':'owner'},
            'networks':{'overseas':None}}}}
        original = copy.deepcopy(before)
        overlay = d.overlay(before,'new')
        self.assertEqual(before,original)
        api,publisher = overlay['services']['api'],overlay['services']['skill-publisher']
        self.assertEqual(api['volumes'],[d.mount(d.p.SOCKET_ROOT,d.p.SOCKET_ROOT,True)])
        self.assertEqual(publisher['user'],'0:0')
        self.assertEqual(len(publisher['volumes']),3)
        self.assertNotIn('ports',publisher)
        self.assertNotIn('must-not-copy',json.dumps(publisher))
        self.assertEqual(publisher['environment']['OVERSEAS_SKILL_TOGGLE_OWNER_ID'],'owner')
        self.assertEqual(publisher['environment']['OVERSEAS_DATABASE_URL'],'synthetic-db')
        self.assertEqual(publisher['networks'],{'overseas':None})

    def test_only_catalog_readers_advance_without_migration(self):
        self.assertEqual(r.NATIVE_FILES,{'app/overseas/management/'+n+'.py' for n in (
            'installed_catalog','installed_tree')})
        self.assertEqual(r.FILES,{'app/overseas/management/'+n+'.py' for n in (
            'router','installed_catalog','installed_tree','skill_transfer_schema','skill_transfer_store',
            'skill_publisher','skill_transfer_client','skill_transfer_router','skill_publication','skill_downloads')})
        baseline_spec = importlib.util.spec_from_file_location('folders_baseline',
            Path(__file__).with_name('skill-folders-baseline.py'))
        baseline = importlib.util.module_from_spec(baseline_spec)
        baseline_spec.loader.exec_module(baseline)
        self.assertEqual(baseline.FILES,r.FILES)
        self.assertEqual(baseline.NATIVE_FILES,r.NATIVE_FILES)
        self.assertEqual((r.OLD_REVISION,r.REVISION),('overseas_0026','overseas_0026'))
        self.assertNotIn('sku-database',r.HELPERS)
        self.assertTrue(all(n.startswith('app/overseas/management/') for n in r.FILES))

    def test_active_import_never_stops_api(self):
        with patch.object(d,'state',return_value=({'oldId':'old'},None)),\
                patch.object(r,'inspect',return_value={'Id':'old'}),patch.object(r,'sql',return_value='1'),\
                patch.object(r,'run') as run:
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(RuntimeError,'Draft imports'):
                    d.gate(Path(directory))
            run.assert_not_called()

    def test_recovery_helper_is_required_and_has_no_independent_runtime(self):
        self.assertIn('skill-folders-recovery',r.HELPERS)
        self.assertNotIn('r',vars(d.recovery))
        self.assertNotIn('p',vars(d.recovery))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.package(root)
            self.assertEqual(r.verify_package(root),manifest)
            del manifest['files']['scripts/release/skill-folders-recovery.py']
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'Incomplete package'):
                r.verify_package(root)

    def test_recovery_delegates_with_current_runtime_and_guards(self):
        for name,args in (
            ('stop_publisher',({'image':'release'},r,d.p)),
            ('recover_before_switch',(Path('isolated-work'),r,d.p,d.state)),
            ('rollback',(Path('isolated-work'),r,d.p,d.state,d.imports_idle)),
        ):
            with self.subTest(action=name),patch.object(d.recovery,name,return_value='delegated') as action:
                self.assertEqual(getattr(d,name)(args[0]),'delegated')
                action.assert_called_once_with(*args)

    def test_gateway_helper_is_mandatory_in_release_package(self):
        self.assertIn('skill-folders-gateway',r.HELPERS)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.package(root)
            del manifest['files']['scripts/release/skill-folders-gateway.py']
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'Incomplete package'):
                r.verify_package(root)

    def test_recovery_candidate_rejection_precedes_host_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.package(root,'candidate')
            with patch.object(d.sku,'state',return_value=({},root)),patch.object(r,'run') as run:
                for action in (d.recover_before_switch,d.rollback):
                    with self.subTest(action=action.__name__),self.assertRaisesRegex(RuntimeError,'Candidate'):
                        action(root)
                run.assert_not_called()

    def test_rollback_uses_callers_import_guard_before_stopping_api(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'API_SWITCH_STARTED').touch()
            with patch.object(d,'state',return_value=({'image':'new','oldImage':'old'},None)) as state,\
                    patch.object(r,'inspect',return_value={'Image':'new','State':{'Running':True}}),\
                    patch.object(d,'imports_idle',side_effect=RuntimeError('Draft imports active')) as idle,\
                    patch.object(r,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'Draft imports'):
                    d.rollback(root)
                state.assert_called_once_with(root,tested=True,release=True)
                idle.assert_called_once_with()
                run.assert_not_called()

if __name__=='__main__':
    unittest.main()
