"""Gateway regressions: no host or network calls escape these mocks."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('folders_deploy',Path(__file__).with_name('skill-folders-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
g = d.r.helper('skill-folders-gateway')


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.clock = patch.object(g.time,'monotonic',side_effect=lambda:self.now)
        self.sleep = patch.object(g.time,'sleep',side_effect=self.advance)
        self.clock.start()
        self.sleep.start()
        self.addCleanup(self.clock.stop)
        self.addCleanup(self.sleep.stop)
        self.identity = 'a'*64
        self.data = {'protected':{'containers':{g.WEB:{'id':self.identity,'image':'image','running':True}}}}
        self.live = dict(Id=self.identity,Image='image',Name='/'+g.WEB,State={'Running':True},
            Config={'Labels':{'com.docker.compose.project':'hengxin-vps-staging','com.docker.compose.service':'web'}})
        self.good = json.dumps({'status':'ready','checks':{'postgresql':'up','redis':'up','minio':'up'}})+'\n200'
        self.r = SimpleNamespace(require=d.r.require,run=Mock(side_effect=self.host))

    def advance(self,seconds):
        self.now += seconds

    def host(self,*args,**kwargs):
        if args[:2]==('docker','inspect'):
            return json.dumps([self.live])
        return self.good if args[0]=='curl' else ''

    def test_only_pinned_web_is_mutated_once_after_config_test(self):
        g.refresh(self.r,self.data)
        calls = [c.args for c in self.r.run.call_args_list]
        self.assertEqual(calls[:3],[('docker','inspect',g.WEB),
            ('docker','exec',self.identity,'nginx','-t'),
            ('docker','exec',self.identity,'nginx','-s','reload')])
        self.assertEqual(len(calls),4)
        self.assertEqual(calls[3][-1],g.READY)

    def test_identity_drift_never_executes_nginx(self):
        self.live['Id'] = 'b'*64
        with self.assertRaisesRegex(RuntimeError,'identity drift'):
            g.refresh(self.r,self.data)
        self.assertEqual(self.r.run.call_count,1)

    def test_config_failure_never_reloads_or_probes(self):
        self.r.run.side_effect = [json.dumps([self.live]),RuntimeError('nginx config invalid')]
        with self.assertRaisesRegex(RuntimeError,'config invalid'):
            g.refresh(self.r,self.data)
        self.assertEqual(self.r.run.call_count,2)

    def test_public_502_never_succeeds_or_reloads_twice(self):
        def host(*args,**kwargs):
            if args[0]=='curl':
                raise RuntimeError('HTTP 502')
            return self.host(*args,**kwargs)
        self.r.run.side_effect = host
        with self.assertRaisesRegex(RuntimeError,'deadline') as caught:
            g.refresh(self.r,self.data,timeout=1)
        self.assertIn('HTTP 502',str(caught.exception.__cause__))
        self.assertEqual(sum(c.args[-2:]==('-s','reload') for c in self.r.run.call_args_list),1)
        self.assertEqual(self.now,1)

    def test_invalid_readiness_payload_and_non_200_are_rejected(self):
        for raw in ('<html>OK</html>\n200','{}\n200',self.good.replace('up','down',1),
                    self.good.replace('ready','unavailable'),self.good.replace('200','302'),
                    '{"status":"ready","checks":{}}\n200'):
            with self.subTest(raw=raw):
                self.now = 0
                self.r.run.return_value = raw
                self.r.run.side_effect = None
                with self.assertRaisesRegex(RuntimeError,'deadline'):
                    g.readiness(self.r,timeout=1)

    def test_inspect_config_reload_and_probe_share_one_deadline(self):
        def host(*args,**kwargs):
            self.advance(1)
            return self.host(*args,**kwargs)
        self.r.run.side_effect = host
        g.refresh(self.r,self.data,timeout=6)
        self.assertEqual([c.kwargs['timeout'] for c in self.r.run.call_args_list],[6,5,4,3])
        self.now = 0
        self.r.run.reset_mock()
        with self.assertRaisesRegex(RuntimeError,'deadline'):
            g.refresh(self.r,self.data,timeout=2)
        self.assertEqual(self.r.run.call_count,2)  # Deadline prevents reload after a slow config test.


class ReleaseGatewayPaths(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.data = dict(manifest='manifest',image='new',oldImage='old',oldId='original',compose={},
            protected={'skills':{}},patch={},environment={'api':'env'})
        self.gateway = Mock()
        self.helpers = Mock()
        def helper(name):
            return self.gateway if name=='skill-folders-gateway' else self.helpers
        for target,name,kwargs in (
            (d,'state',{'return_value':(self.data,None)}),(d.r,'helper',{'side_effect':helper}),
            (d.r,'run',{'return_value':''}),(d.r,'worker',{}),(d.r,'private',{}),
            (d.r.a,'compose',{'return_value':'{}'}),(d.r.a,'check_live_config',{}),
            (d.recovery,'stop_publisher',{}),(d,'imports_idle',{}),
            (d.r.b,'tree',{'return_value':{}}),(d.r,'hashes',{'return_value':{}})):
            item = patch.object(target,name,**kwargs)
            item.start()
            self.addCleanup(item.stop)

    def test_switch_refresh_failure_prevents_verification(self):
        with patch.object(d,'publisher_ready'),patch.object(d,'verify') as verify:
            self.gateway.refresh.side_effect = RuntimeError('Public API 502')
            with self.assertRaisesRegex(RuntimeError,'502'):
                d.api(self.work)
            verify.assert_not_called()
            self.gateway.refresh.assert_called_once_with(d.r,self.data)

    def test_verify_requires_public_health_before_success_marker(self):
        live = dict(Image='new',State={'Running':True},Config={'Env':[]},Id='new-id')
        self.gateway.readiness.side_effect = RuntimeError('Public API 502')
        with patch.object(d.r,'inspect',return_value=live),patch.object(d,'publisher_ready'),\
                patch.object(d.r,'environment_hash',return_value='env'):
            d.r.run.return_value = 'READ_ONLY_CATALOG_OK'
            with self.assertRaisesRegex(RuntimeError,'502'):
                d.verify(self.work)
            d.r.private.assert_not_called()
            self.gateway.refresh.assert_not_called()  # verify is read-only.

    def test_both_recovery_paths_refresh_before_writing_success(self):
        for action,marker in ((d.recover_before_switch,'RECOVERED_BEFORE_SWITCH'),(d.rollback,'ROLLED_BACK')):
            for fail in (False,True):
                with self.subTest(action=action.__name__,failure=fail):
                    self.gateway.refresh.reset_mock()
                    self.gateway.refresh.side_effect = RuntimeError('Public API 502') if fail else None
                    d.r.private.reset_mock()
                    if action==d.rollback:
                        (self.work/'API_SWITCH_STARTED').touch()
                        states = [dict(Image='new',State={'Running':False})]*2+[
                            dict(Image='old',State={'Running':True})]
                    else:
                        (self.work/'GATE_STARTED').write_text('{"node":"worker"}')
                        states = [dict(Id='original',State={'Running':False})]
                    with patch.object(d.r,'inspect',side_effect=states):
                        if fail:
                            with self.assertRaisesRegex(RuntimeError,'502'):
                                action(self.work)
                            d.r.private.assert_not_called()
                        else:
                            action(self.work)
                            self.assertEqual(d.r.private.call_args.args[0],self.work/marker)
                    self.gateway.refresh.assert_called_once_with(d.r,self.data)

    def test_rollback_import_recheck_failure_refreshes_restarted_api(self):
        (self.work/'API_SWITCH_STARTED').touch()
        d.imports_idle.side_effect = [None,RuntimeError('imports became active')]
        with patch.object(d.r,'inspect',return_value=dict(Image='new',State={'Running':False})):
            with self.assertRaisesRegex(RuntimeError,'imports became active'):
                d.rollback(self.work)
        d.r.run.assert_called_once_with('docker','start',d.r.API)
        self.gateway.refresh.assert_called_once_with(d.r,self.data)
        d.r.private.assert_not_called()


if __name__=='__main__':
    unittest.main()
