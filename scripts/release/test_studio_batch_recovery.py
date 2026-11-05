"""Recovery order, admission races and candidate immutability."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


d = load('studio-batch-deploy')
r = d.r
recovery = load('studio-batch-recovery')


class RecoveryTests(unittest.TestCase):
    def test_candidate_rejected_before_any_production_recovery_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            with patch.object(d.sku,'state',return_value=({},work)), \
                 patch.object(r,'verify_package',return_value={'mode':'candidate'}), \
                 patch.object(r,'run') as run:
                for action in (d.rollback,d.recover_before_switch):
                    with self.assertRaisesRegex(RuntimeError,'test-only'):
                        action(work)
                run.assert_not_called()

    def test_wrong_recovery_phase_does_not_touch_host(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            with patch.object(r,'inspect') as inspect:
                with self.assertRaisesRegex(RuntimeError,'Wrong recovery phase'):
                    recovery.recover(work,r,Mock(return_value=({},work)),Mock(),False)
                inspect.assert_not_called()

    def test_submission_race_restarts_current_api_and_refreshes_gateway_without_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work/'API_SWITCH_STARTED').touch()
            r.private(work/'GATE_STARTED', {'node':'node'})
            data = {'image':'new','oldImage':'old','manifest':'m'}
            gateway = SimpleNamespace(refresh=Mock())
            with patch.object(r,'inspect',side_effect=[{'Image':'new','State':{'Running':True}},
                                                       {'State':{'Running':False}}]), \
                 patch.object(recovery,'settled'), patch.object(recovery,'worker_idle'), \
                 patch.object(r,'worker'), patch.object(r,'run') as run, \
                 patch.object(r,'helper',return_value=gateway),patch.object(r.a,'compose') as compose:
                with self.assertRaisesRegex(RuntimeError,'raced import'):
                    recovery.recover(work,r,Mock(return_value=(data,work)),
                        Mock(side_effect=[None,RuntimeError('raced import')]),False)
                compose.assert_not_called()
                self.assertEqual(run.call_args.args,('docker','start',r.API))
                gateway.refresh.assert_called_once_with(r,data)

    def test_native_restoration_precedes_original_api_start_and_gateway_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work/'NATIVE_PATCH_STARTED').touch()
            (work/'NATIVE_STOP_STARTED').touch()
            r.private(work/'GATE_STARTED', {'node':'node'})
            data = {'oldId':'old-id','image':'new','oldImage':'old','manifest':'manifest',
                    'patch':{'module':{'baseline':'hash'}},'compose':{},
                    'environment':{'api':'envhash'},'protected':{'skills':{}}}
            events = []
            native = SimpleNamespace(pid=lambda unit:0)
            batch_native = SimpleNamespace(restore=lambda *a:events.append('native-restored'),
                                           verify_baseline=lambda *a:events.append('native-verified'))
            gateway = SimpleNamespace(refresh=lambda *a:events.append('gateway'))
            helpers = {'sku-native':native,'studio-batch-native':batch_native,'skill-folders-gateway':gateway}
            old = {'Id':'old-id','Image':'old','State':{'Running':True},'Config':{'Env':[]}}
            with patch.object(r,'inspect',side_effect=[{**old,'State':{'Running':False}},
                                                       {'State':{'Running':False}},old]), \
                 patch.object(r,'helper',side_effect=lambda name:helpers[name]), patch.object(recovery,'settled'), \
                 patch.object(recovery,'stop_native',side_effect=lambda *a:events.append('native-stopped')), \
                 patch.object(r,'hashes',return_value={'module':'hash'}), \
                 patch.object(r,'run',side_effect=lambda *a,**k:events.append('api-start')), \
                 patch.object(r.a,'compose',return_value='{}'),patch.object(r.a,'check_live_config'), \
                 patch.object(r,'environment_hash',return_value='envhash'), \
                 patch.object(r,'worker_probe'),patch.object(r.b,'tree',return_value={}):
                recovery.recover(work,r,Mock(return_value=(data,work)),Mock(),True)
            self.assertEqual(events,['native-stopped','native-restored','native-verified','api-start','gateway'])
            self.assertTrue((work/'RECOVERED_BEFORE_SWITCH').exists())

    def test_dirty_source_cannot_create_even_a_candidate_package(self):
        package = load('studio-batch-package')
        common = SimpleNamespace(git=Mock(return_value=b'dirty.py'))
        with patch.object(package.r,'helper',return_value=common), \
             patch.object(package.subprocess,'check_output') as identity:
            for candidate in (True,False):
                with self.assertRaisesRegex(RuntimeError,'Commit release sources first'):
                    package.build(Path('unused'),Path('unused'),candidate=candidate)
            identity.assert_not_called()


if __name__ == '__main__':
    unittest.main()
