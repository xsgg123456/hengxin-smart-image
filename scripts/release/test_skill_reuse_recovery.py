"""Regression coverage for restrictive umasks and failures before admission closes."""
from contextlib import nullcontext
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_skill_reuse_release as fixtures
from test_skill_reuse_release import digest, load, private, require


class RecoveryTests(unittest.TestCase):
    setUp = fixtures.ReleaseTests.setUp

    def recovery_fixture(self):
        deploy = load('skill-reuse-deploy')
        work = self.root/'work'
        store = self.root/'store'
        work.mkdir()
        store.mkdir()
        source = self.root/'app.py'
        source.write_text('original')
        proxy = self.root/'proxy.conf'
        proxy.write_text('original proxy')
        data = dict(manifest='m',proxies={'edge':{'path':str(proxy),'sha256':digest(proxy)}},
            protected={'units':{'worker':{'pid':10,'cwd':str(self.root),'source':{'app.py':digest(source)}}}},
            native={'units':{'worker':{'files':{'app.py':digest(source)}}}},
            environment={'native':{'worker':'original environment'}})
        native = Mock()
        native.safe.side_effect = lambda path:path
        native.pid.return_value = 10
        recovery = load('skill-reuse-native')
        gate = Mock()
        helpers = {'sku-native':native,'skill-reuse-native':recovery,'skill-reuse-gate':gate,
            'release-retention-state':SimpleNamespace(Store=lambda:SimpleNamespace(root=store,locked=nullcontext))}
        runtime = SimpleNamespace(require=require,private=private,digest=digest,UNITS=('worker',),
            helper=helpers.__getitem__,worker=Mock(),native_environment=lambda unit:'original environment',
            run=Mock(side_effect=lambda *args,**kwargs:'active' if 'ActiveState' in args else '0'))
        recovery.r = deploy.r = runtime
        return deploy,work,store/'native-release-owner.json',data,source,proxy,native,gate

    def cli(self,deploy,work,action):
        with patch.object(sys,'argv',['deploy',action,'--work',str(work)]),\
             patch.object(deploy.os,'geteuid',return_value=0,create=True),\
             patch.object(deploy.os,'umask'):
            deploy.main()

    def test_busy_initial_gate_then_recover_releases_owner_without_mutation(self):
        deploy,work,claim,data,source,proxy,native,gate = self.recovery_fixture()
        with patch.object(deploy,'state',return_value=(data,self.root)):
            # Run real main -> gate -> idle. DB background jobs are nonzero.
            deploy.r.DB = ('database','user','db')
            deploy.r.run.return_value = '1'
            deploy.r.run.side_effect = None
            with self.assertRaisesRegex(RuntimeError,'Background work remains'):
                self.cli(deploy,work,'gate')
            self.assertTrue(claim.exists())
            self.assertFalse((work/'GATE_STARTED').exists())
            deploy.r.run.side_effect = lambda *args,**kwargs:'active' if 'ActiveState' in args else '0'
            self.cli(deploy,work,'recover')
        self.assertFalse(claim.exists())
        self.assertEqual(source.read_text(),'original')
        self.assertEqual(proxy.read_text(),'original proxy')
        gate.set_gate.assert_not_called()
        native.start.assert_not_called()
        native.stop.assert_not_called()
        deploy.r.worker.assert_not_called()
        self.assertFalse((work/'RECOVERED').exists())

    def test_missing_gate_marker_with_cutover_evidence_retains_owner(self):
        deploy,work,claim,data,_,_,native,gate = self.recovery_fixture()
        private(claim,{'work':str(work.resolve())})
        for marker in ('PROXY_DRAIN.json','INTAKE_CLOSED','gate.json','NATIVE_STOP_STARTED',
                       'NATIVE_PATCH_STARTED','NATIVE_RECOVERY.json','CONVERSATION_BASELINE',
                       'native-backup.json','RESUMED'):
            with self.subTest(marker=marker):
                (work/marker).write_text('{}')
                with patch.object(deploy,'state',return_value=(data,self.root)),\
                     self.assertRaisesRegex(RuntimeError,'cutover evidence'):
                    self.cli(deploy,work,'recover')
                self.assertTrue(claim.exists())
                (work/marker).unlink()
        gate.set_gate.assert_not_called()
        native.start.assert_not_called()

    def test_ungated_recovery_rejects_changed_originals(self):
        deploy,work,claim,data,source,proxy,native,gate = self.recovery_fixture()
        private(claim,{'work':str(work.resolve())})
        for drift in ('source','proxy','pid','pending job','inactive','preflight'):
            with self.subTest(drift=drift):
                original_source,original_proxy = source.read_bytes(),proxy.read_bytes()
                if drift == 'source': source.write_text('changed')
                if drift == 'proxy': proxy.write_text('changed')
                native.pid.return_value = 11 if drift == 'pid' else 10
                native.preflight.side_effect = RuntimeError('preflight drift') if drift == 'preflight' else None
                deploy.r.run.side_effect = lambda *args,**kwargs: (
                    ('inactive' if drift == 'inactive' else 'active') if 'ActiveState' in args
                    else ('17' if drift == 'pending job' else '0'))
                with patch.object(deploy,'state',return_value=(data,self.root)),self.assertRaises(RuntimeError):
                    self.cli(deploy,work,'recover')
                self.assertTrue(claim.exists())
                source.write_bytes(original_source)
                proxy.write_bytes(original_proxy)
        gate.set_gate.assert_not_called()

    def test_started_gate_cannot_use_ungated_cancellation(self):
        deploy,work,claim,data,_,_,native,gate = self.recovery_fixture()
        private(claim,{'work':str(work.resolve())})
        private(work/'GATE_STARTED',{'node':'worker','manifest':'m'})
        gate.set_gate.side_effect = RuntimeError('existing recovery must close gate')
        with patch.object(deploy,'state',return_value=(data,self.root)),\
             patch.object(deploy,'cancel_ungated') as cancel,\
             self.assertRaisesRegex(RuntimeError,'existing recovery'):
            self.cli(deploy,work,'recover')
        cancel.assert_not_called()
        gate.set_gate.assert_called_once_with(work,data,True)
        self.assertTrue(claim.exists())


class CandidatePermissionTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0,
                         'Requires Linux root for actual directory ownership')
    def test_invoke_private_scratch_owned_by_execution_uid(self):
        import pwd
        import tempfile
        runner = load('skill-reuse-test')
        user = pwd.getpwnam('nobody')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner.r = SimpleNamespace(require=require,private=private)
            for as_root in (False, True):
                label = 'root' if as_root else 'service'
                expected_uid,expected_gid = (0,0) if as_root else (user.pw_uid,user.pw_gid)
                def execute(command,**kwargs):
                    scratch = next(root.glob(label+'-*'))
                    info = scratch.stat()
                    self.assertEqual((info.st_uid,info.st_gid),(expected_uid,expected_gid))
                    self.assertEqual(info.st_mode & 0o777,0o700)
                    self.assertIn('assert os.getuid()=='+str(expected_uid),' '.join(command))
                    return SimpleNamespace(returncode=0,stdout='2 passed',stderr='')
                with patch.object(pwd,'getpwnam',return_value=user),\
                     patch.object(runner.subprocess,'run',side_effect=execute):
                    runner.invoke(root,root,root,root,label,Path(sys.executable),as_root=as_root)

    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0,
                         'Requires Linux root to exercise a real unprivileged UID')
    def test_umask_077_candidate_and_vendor_importable_by_nobody(self):
        import pwd
        import tempfile
        runner = load('skill-reuse-test')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o755)
            production,source,work = [root/name for name in ('production','source','work')]
            for path in (production/'app',source/'native/app',work):
                path.mkdir(parents=True)
            (production/'app/__init__.py').write_text('')
            (source/'native/app/materials.py').write_text('VALUE = 42')
            dependencies = root/'dependencies'
            names = ('pytest','_pytest','pluggy','iniconfig','packaging','pygments')
            for name in names:
                path = dependencies/name
                path.mkdir(parents=True)
                (path/'__init__.py').write_text('VALUE = 43')
            (dependencies/'py.py').write_text('VALUE = 44')
            (dependencies/'pytest/__init__.py').write_text('import py\nVALUE = py.VALUE - 1')
            nobody = pwd.getpwnam('nobody')
            calls = []

            def docker(*args):
                if args[1] == 'run':
                    return json.dumps({**{name:str(dependencies/name) for name in names},
                                       'py':str(dependencies/'py.py')})
                if args[1] == 'create': return 'test-container'
                if args[1] == 'cp':
                    original = Path(args[2].split(':',1)[1])
                    if original.is_dir(): shutil.copytree(original,args[3])
                    else: shutil.copyfile(original,args[3])
                return ''

            def invoke(_work,install,_source,target,label,python,as_root=False):
                # Actual kernel DAC traversal and Python imports as a different UID.
                # No mocked chmod or access() result can make this assertion pass.
                code = ('import sys,os; assert os.getuid()==int(sys.argv[1]); '
                        'import app.materials,pytest; '
                        'assert app.materials.VALUE==42 and pytest.VALUE==43')
                result = subprocess.run([sys.executable,'-B','-c',code,str(nobody.pw_uid)],
                    cwd=install,env={'PYTHONPATH':str(install)+':'+str(target/'vendor'),
                                    'PYTHONDONTWRITEBYTECODE':'1'},
                    user=nobody.pw_uid,group=nobody.pw_gid,extra_groups=[],
                    capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stderr)
                calls.append(label)

            runner.r = SimpleNamespace(require=require,private=private,run=docker,
                NATIVE_FILES={'app/materials.py'},b=SimpleNamespace(tree=lambda path:{}),
                helper=lambda name:SimpleNamespace(baseline_roots=lambda data:{str(production):{}}))
            real_path = Path
            old_umask = os.umask(0o077)
            try:
                with patch.object(runner,'Path',side_effect=lambda path:root if path == '/opt' else real_path(path)),\
                     patch.object(runner,'invoke',side_effect=invoke):
                    runner.candidate(work,{'manifest':'a'*64,'api':{'image':'fixture'}},source)
            finally:
                os.umask(old_umask)
            self.assertEqual(calls,['candidate','candidate-root'])
            target = root/('hengxin-skill-reuse-test-'+'a'*16)
            self.assertEqual(target.stat().st_mode & 0o777,0o755)
            self.assertEqual((target/'vendor').stat().st_mode & 0o777,0o755)
            self.assertEqual((target/'vendor/py.py').stat().st_mode & 0o777,0o644)


if __name__ == '__main__':
    unittest.main()
