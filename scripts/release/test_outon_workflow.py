"""Offline workflow configuration tests; no Docker or systemd calls reach the host."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


w = load('outon-workflow')
IDS = [f'00000000-0000-0000-0000-{n:012d}' for n in range(1,6)]


class WorkflowTests(unittest.TestCase):
    def fixture(self, root):
        rows = [dict(id=value, name='fixture', status='active', directoryState='enrolled', role='designer')
                for value in IDS]
        path = root/'workflow-collaborators.private.json'
        path.write_text(json.dumps({'members':rows}))
        data = {'manifest':'release', 'protected':{'units':{u:{'pid':10+i,'files':{}} for i,u in enumerate(w.r.UNITS)}}}
        return rows, path, data

    def test_binding_requires_exactly_five_distinct_canonical_designer_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows, path, _ = self.fixture(root)
            self.assertEqual(w.binding(root), IDS)
            for invalid in (rows[:4], rows+[rows[0]], [rows[0]]*5,
                            [{**rows[0],'role':'operator'},*rows[1:]],
                            [{**rows[0],'status':'disabled'},*rows[1:]],
                            [{**rows[0],'directoryState':'legacy_unconfirmed'},*rows[1:]],
                            [{**rows[0],'id':'not-uuid'},*rows[1:]]):
                path.write_text(json.dumps({'members':invalid}))
                with self.assertRaises((RuntimeError, ValueError)):
                    w.binding(root)

    def test_overlay_changes_only_authorized_key_and_image(self):
        before = {'services':{'api':{'image':'old','environment':{
            'OVERSEAS_FULL_ACCESS_MEMBER_IDS':'["existing"]','OVERSEAS_SKILL_TOGGLE_OWNER_ID':'owner',
            'OTHER':'secret'}},'domestic':{'image':'untouched'}}}
        config = {'memberIds':IDS}
        overlay = w.overlay(before,'new',config)
        self.assertEqual(set(overlay['services']), {'api'})
        self.assertEqual(set(overlay['services']['api']['environment']), {w.KEY})
        after = copy.deepcopy(before)
        after['services']['api']['image'] = 'new'
        after['services']['api']['environment'][w.KEY] = w.encoded(IDS)
        w.check_overlay(before, after, 'new', config)
        after['services']['api']['environment']['OVERSEAS_FULL_ACCESS_MEMBER_IDS'] = '[]'
        with self.assertRaisesRegex(RuntimeError,'unrelated'):
            w.check_overlay(before, after, 'new', config)
        self.assertNotIn(w.KEY, before['services']['api']['environment'])

    def test_preexisting_unreviewed_grants_are_rejected(self):
        w.existing_grant({}, IDS)
        w.existing_grant({w.KEY:json.dumps(list(reversed(IDS)))}, IDS)
        for value in ('["unknown"]', json.dumps(IDS+IDS), '{}', 'true'):
            with self.assertRaisesRegex(RuntimeError,'explicit review'):
                w.existing_grant({w.KEY:value}, IDS)

    def test_probe_rejects_effective_admin_disabled_and_missing_members(self):
        rows = [dict(id=v,status='active',directoryState='enrolled',roles=['designer']) for v in IDS]
        with patch.object(w.r,'run',return_value=json.dumps(rows)) as run:
            w.probe(IDS)
        command = run.call_args.args
        self.assertEqual(command[:3], ('docker','exec',w.r.API))
        code = command[command.index('-c')+1]
        self.assertIn('SET TRANSACTION READ ONLY',code)
        compile(code,'workflow-probe','exec')
        for bad in (rows[:4], [{**rows[0],'roles':['super_admin']},*rows[1:]],
                    [{**rows[0],'status':'disabled'},*rows[1:]],
                    [{**rows[0],'roles':['operator']},*rows[1:]]):
            with patch.object(w.r,'run',return_value=json.dumps(bad)), self.assertRaisesRegex(RuntimeError,'designers'):
                w.probe(IDS)

    def test_native_files_have_no_other_setting_and_use_persistent_dropins(self):
        files = w.native_files(IDS)
        self.assertEqual(len(files), 3)
        self.assertEqual(files[str(w.ENV_FILE)], w.KEY+"='"+w.encoded(IDS)+"'\n")
        for name, value in files.items():
            if name != str(w.ENV_FILE):
                self.assertTrue(Path(name).as_posix().startswith('/etc/systemd/system/'))
                self.assertEqual(value, '[Service]\nEnvironmentFile='+str(w.ENV_FILE)+'\n')

    def test_prepare_only_records_private_binding_and_native_environment_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, _, data = self.fixture(root)
            files = {str(root/'env'):w.KEY+'=[]\n',str(root/'drop'):'[Service]\n'}
            env = {'OVERSEAS_FULL_ACCESS_MEMBER_IDS':'["unrelated"]','OVERSEAS_SKILL_TOGGLE_OWNER_ID':'owner'}
            with patch.object(w,'probe'),patch.object(w,'environment',return_value=env), \
                 patch.object(w,'native_files',return_value=files),patch.object(w.r,'run') as run:
                config = w.prepare(root,data,{'Config':{'Env':[]}})
            run.assert_not_called()
            self.assertFalse((root/'env').exists())
            self.assertEqual(config['memberIds'],IDS)
            self.assertNotIn('owner',json.dumps(config))
            data['workflow'] = config
            with patch.object(w,'native_files',return_value=files),patch.object(w,'native_inventory',return_value=set()):
                w.guard(root,data)
                (root/'env').write_text('unexpected')
                with self.assertRaisesRegex(RuntimeError,'drift'):
                    w.guard(root,data)

    def test_install_failure_retains_started_marker_and_blocks_blind_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, _, data = self.fixture(root)
            data['workflow'] = {'memberIds':IDS,'files':{'file':'digest'}}
            with patch.object(w,'guard'),patch.object(w.r,'helper'), \
                 patch.object(w,'native_files',side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    w.install(root,data)
            self.assertTrue((root/'WORKFLOW_NATIVE_STARTED').exists())
            with patch.object(w,'guard'),self.assertRaisesRegex(RuntimeError,'no blind retry'):
                w.install(root,data)

    def test_native_inventory_rejects_an_unapproved_new_dropin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, _, data = self.fixture(root)
            with patch.object(w,'probe'),patch.object(w,'environment',return_value={}):
                data['workflow'] = w.prepare(root,data,{'Config':{'Env':[]}})
            with patch.object(w,'native_inventory',return_value={'/etc/systemd/system/foreign.conf'}), \
                 self.assertRaisesRegex(RuntimeError,'inventory drift'):
                w.guard(root,data)

    def test_native_verification_rejects_grant_or_unrelated_environment_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, _, data = self.fixture(root)
            env = {'HX_BUSINESS_CONTEXT':'overseas','OVERSEAS_FULL_ACCESS_MEMBER_IDS':'["old"]'}
            data['workflow'] = {'memberIds':IDS,'nativeEnvironment':{u:w.protected_environment(env) for u in w.r.UNITS}}
            (root/'WORKFLOW_NATIVE_INSTALLED').write_text('proof')
            good = {**env,w.KEY:w.encoded(IDS)}
            with patch.object(w,'guard'),patch.object(w.r,'helper'),patch.object(w,'environment',return_value=good):
                w.verify_native(root,data)
            for bad, message in (({**good,w.KEY:'[]'},'grant mismatch'),
                                 ({**good,'OVERSEAS_FULL_ACCESS_MEMBER_IDS':'[]'},'Unrelated')):
                with patch.object(w,'guard'),patch.object(w.r,'helper'), \
                     patch.object(w,'environment',return_value=bad),self.assertRaisesRegex(RuntimeError,message):
                    w.verify_native(root,data)


if __name__ == '__main__':
    unittest.main()
