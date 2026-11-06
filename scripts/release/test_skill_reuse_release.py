"""Native release scope, absent-original recovery, immutable API and admission safety."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-','_'),Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(value,message):
    if not value:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private(path,value):
    path.write_text(json.dumps(value))


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_proxy_scope_and_ambiguity(self):
        gate = load('skill-reuse-gate')
        gate.r = SimpleNamespace(require=require)
        original = 'location ^~ /api/overseas/v1/ { proxy_pass http://api; }\nlocation /api/v1/ { keep; }'
        changed = gate.closed_config(original)
        self.assertIn('location /api/v1/ { keep; }',changed)
        self.assertIn('return 503',changed)
        for invalid in ('location /api/v1/ {}',original+original,changed):
            with self.assertRaises(RuntimeError):
                gate.closed_config(invalid)

    def test_old_nginx_workers_must_exit(self):
        gate = load('skill-reuse-gate')
        gate.r = SimpleNamespace(require=require,run=Mock(return_value='PID COMMAND\n123 nginx: worker process\n124 nginx: master process'))
        self.assertEqual(gate.workers('container',float('inf')),{'123'})
        with self.assertRaises(RuntimeError):
            gate.remaining(0)

    def fixture(self):
        native = load('skill-reuse-native')
        app = self.root/'install'
        work = self.root/'work'
        work.mkdir()
        old = 'app/overseas/execution/materials.py'
        new = 'app/overseas/execution/skill_cache.py'
        path = app/old
        path.parent.mkdir(parents=True)
        path.write_bytes(b'original')
        files = {old:digest(path),new:None}
        primitives = SimpleNamespace(safe=lambda p:p,baseline_roots=lambda data:{str(app):files})
        native.r = SimpleNamespace(require=require,digest=digest,private=private,helper=lambda name:primitives)
        return native,app,work,files

    def test_backups_record_absent_and_preserve_old_bytes(self):
        native,app,work,files = self.fixture()
        native.backup(work,{})
        records = native.records(work,{})
        absent = next(v for v in records if v['sha256'] is None)
        old = next(v for v in records if v['sha256'])
        self.assertIsNone(absent['backup'])
        self.assertEqual(Path(old['backup']).read_bytes(),b'original')
        self.assertEqual((app/'app/overseas/execution/materials.py').read_bytes(),b'original')
        with self.assertRaises(RuntimeError):
            native.backup(work,{})

    def test_backup_tamper_missing_or_added_record_rejected(self):
        native,app,work,files = self.fixture()
        native.backup(work,{})
        records = native.records(work,{})
        private(work/'native-backup.json',records[:-1])
        with self.assertRaises(RuntimeError):
            native.records(work,{})
        private(work/'native-backup.json',records)
        Path(next(v['backup'] for v in records if v['backup'])).write_bytes(b'changed')
        with self.assertRaises(RuntimeError):
            native.records(work,{})

    def test_recovery_guard_accepts_absent_original_but_rejects_restart(self):
        runtime = load('skill-reuse-runtime')
        work = self.root
        app = self.root/'install'
        name = 'app/new.py'
        new = 'a'*64
        saved = dict(cwd=str(app),source={},files={},pid=10)
        data = dict(manifest='m',protected={'units':{'unit':saved}},
            native={'units':{'unit':{'files':{name:None}}}},patch={name:{'sha256':new}})
        private(work/'NATIVE_RECOVERY.json',dict(manifest='m',phase='restoring',pids={'unit':10},sources={'unit':{name:new}}))
        primitives = SimpleNamespace(pid=Mock(return_value=0),drop_path=lambda u:work/'missing')
        runtime.r = SimpleNamespace(require=require,UNITS=('unit',),NATIVE_FILES={name},digest=digest,
            b=SimpleNamespace(tree=Mock(return_value={})))
        with patch.object(runtime,'helper',return_value=primitives):
            runtime.guard(work,data)
            primitives.pid.return_value=99
            with self.assertRaises(RuntimeError):
                runtime.guard(work,data)

    def test_recovery_guard_rejects_unrelated_file(self):
        runtime = load('skill-reuse-runtime')
        private(self.root/'NATIVE_RECOVERY.json',dict(manifest='m',phase='restoring',pids={'unit':0},sources={'unit':{'app/new.py':'a'*64}}))
        data = dict(manifest='m',protected={'units':{'unit':dict(cwd=str(self.root),source={},files={},pid=1)}},
            native={'units':{'unit':{'files':{'app/new.py':None}}}},patch={'app/new.py':{'sha256':'a'*64}})
        runtime.r = SimpleNamespace(require=require,UNITS=('unit',),NATIVE_FILES={'app/new.py'},digest=digest,
            b=SimpleNamespace(tree=lambda p:{'unrelated.py':'changed'}))
        primitive = SimpleNamespace(pid=lambda u:0,drop_path=lambda u:self.root/'missing')
        with patch.object(runtime,'helper',return_value=primitive),self.assertRaises(RuntimeError):
            runtime.guard(self.root,data)

    def test_metadata_detects_change_without_reading_private_contents(self):
        preserve = load('skill-reuse-preserve')
        path = self.root/'session.jsonl'
        path.write_bytes(b'full context')
        before = preserve.metadata(self.root)
        with patch.object(Path,'read_bytes',side_effect=AssertionError('must not read secrets')):
            self.assertEqual(preserve.metadata(self.root),before)
        path.write_bytes(b'changed')
        self.assertNotEqual(preserve.metadata(self.root),before)

    def test_api_identity_tracks_restart_even_same_container_and_image(self):
        deploy = load('skill-reuse-deploy')
        live = dict(Id='id',Image='image',State=dict(Running=True,StartedAt='first'))
        deploy.r = SimpleNamespace(inspect=lambda:live,require=require)
        first = deploy.api_identity()
        live['State']['StartedAt']='second'
        self.assertNotEqual(deploy.api_identity(),first)
        live['State']['Running']=False
        with self.assertRaises(RuntimeError):
            deploy.api_identity()

    def test_recovery_pending_job_cannot_reopen_gate(self):
        deploy = load('skill-reuse-deploy')
        private(self.root/'GATE_STARTED',{'node':'worker'})
        gate = Mock()
        native = Mock()
        deploy.r = SimpleNamespace(require=require,private=private,UNITS=('worker',),
            helper=lambda name:gate if name == 'skill-reuse-gate' else native,
            run=lambda *args:'deactivating')
        with patch.object(deploy,'state',return_value=({'manifest':'m'},self.root)),self.assertRaises(RuntimeError):
            deploy.recover(self.root)
        gate.set_gate.assert_called_once_with(self.root,{'manifest':'m'},True)
        native.start.assert_not_called()

    def test_package_required_scope_includes_linux_and_catalog_probe(self):
        runtime = load('skill-reuse-runtime')
        self.assertEqual(len(runtime.r.NATIVE_FILES),3)
        self.assertIn('test_studio_skill_cache_linux.py',runtime.TESTS)
        self.assertIn('skill-reuse-catalog-probe',runtime.HELPERS)
        self.assertNotIn('sku-deploy',runtime.HELPERS)


if __name__ == '__main__':
    unittest.main()
