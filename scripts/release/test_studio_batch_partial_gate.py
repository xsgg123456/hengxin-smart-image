"""Exercise recovery with real worker CLI identity and queue prerequisites."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from test_studio_batch_recovery import load

recovery = load('studio-batch-recovery')
probe = load('studio-batch-worker')
r = load('studio-batch-runtime').r


class PartialGateTests(unittest.TestCase):
    def exercise(self, paused=True, stopped=False, pending=False, imports_busy=False, gate_file=True):
        events, queues = [], ([] if paused else [{'name':'overseas.cli'}])
        worker_pid = 42
        def change(active):
            queues[:] = [{'name':'overseas.cli'}] if active else []
            events.append('resume' if active else 'pause')
            return [{'node':{'ok':'done'}}]
        inspector = SimpleNamespace(stats=lambda:{'node':{'pid':42,'pool':{'max-concurrency':5}}},
            active_queues=lambda:{'node':list(queues)},active=lambda:{'node':[]},
            reserved=lambda:{'node':[]},scheduled=lambda:{'node':[]})
        control = SimpleNamespace(inspect=lambda **kwargs:inspector,
            add_consumer=lambda *a,**k:change(True),cancel_consumer=lambda *a,**k:change(False))
        session = Mock()
        session.__enter__ = Mock(return_value=SimpleNamespace(scalar=lambda query:0))
        session.__exit__ = Mock(return_value=False)
        modules = {'app.overseas.execution.worker':SimpleNamespace(celery_app=SimpleNamespace(control=control)),
            'app.overseas.db':SimpleNamespace(session_factory=lambda:lambda:session),
            'sqlalchemy':SimpleNamespace(text=lambda query:query)}
        def worker(mode, node='-', **kwargs):
            if mode == 'status':
                return probe.status(control,worker_pid,node)
            with patch.dict(sys.modules,modules),patch.object(sys,'argv',['worker',mode,str(worker_pid),node]):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    probe.w.main()
            return json.loads(output.getvalue())
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            r.private(work/'GATE_STARTED',{'node':'node'})
            if gate_file:
                r.private(work/'gate.json',{'node':'node'})
            if stopped:
                (work/'NATIVE_STOP_STARTED').touch()
            data = {'oldId':'old-id','image':'new','oldImage':'old','manifest':'m',
                'patch':{'module':{'baseline':'hash'}},'compose':{},
                'environment':{'api':'envhash'},'protected':{'skills':{}}}
            def start(*args,**kwargs):
                events.append('native-start')
                worker('resume','node')
            native = SimpleNamespace(pid=lambda unit:42 if unit == r.UNITS[0] else (0 if stopped else 43),start=start)
            helpers = {'sku-native':native,
                'studio-batch-native':SimpleNamespace(verify_baseline=lambda *a:events.append('baseline')),
                'skill-folders-gateway':SimpleNamespace(refresh=lambda *a:events.append('gateway'))}
            def run(*args,**kwargs):
                if args[0] == 'systemctl':
                    if args[4] == 'Job':
                        return '123' if pending else '0'
                    return 'inactive' if stopped and args[2] == r.UNITS[1] else 'active'
                events.append('api-start')
            old = {'Id':'old-id','Image':'old','State':{'Running':True},'Config':{'Env':[]}}
            with patch.object(r,'inspect',side_effect=[{**old,'State':{'Running':False}},
                {'State':{'Running':False}},old]),patch.object(r,'helper',side_effect=lambda n:helpers[n]), \
                patch.object(r,'worker',side_effect=worker),patch.object(r,'run',side_effect=run), \
                patch.object(r,'hashes',return_value={'module':'hash'}), \
                patch.object(r.a,'compose',return_value='{}'),patch.object(r.a,'check_live_config'), \
                patch.object(r,'environment_hash',return_value='envhash'),patch.object(r,'worker_probe'), \
                patch.object(r.b,'tree',return_value={}):
                imports = Mock(side_effect=RuntimeError('raced import') if imports_busy else None)
                if pending or imports_busy:
                    with self.assertRaisesRegex(RuntimeError,'pending' if pending else 'raced import'):
                        recovery.recover(work,r,Mock(return_value=(data,work)),imports,True)
                else:
                    recovery.recover(work,r,Mock(return_value=(data,work)),imports,True)
                    self.assertTrue((work/'RECOVERED_BEFORE_SWITCH').exists())
        if pending:
            self.assertEqual(events,[])
            self.assertEqual(queues,[])
        else:
            self.assertEqual(queues,[{'name':'overseas.cli'}])
            self.assertLess(events.index('resume'),events.index('api-start'))
            if stopped:
                self.assertLess(events.index('native-start'),events.index('api-start'))

    def test_pause_succeeded_before_gate_write(self):
        self.exercise(gate_file=False)

    def test_pause_succeeded_before_native_stop(self):
        self.exercise()

    def test_gate_failed_before_pause(self):
        self.exercise(paused=False)

    def test_outbox_stopped_worker_still_paused(self):
        self.exercise(stopped=True)

    def test_stop_job_pending_retains_protection_and_closed_api(self):
        self.exercise(stopped=True,pending=True)

    def test_raced_import_resumes_consumer_before_api(self):
        self.exercise(imports_busy=True)

    def test_status_rejects_wrong_node_pool_and_queue(self):
        for stats,queues in [({'other':{'pid':42,'pool':{'max-concurrency':5}}},[]),
            ({'node':{'pid':42,'pool':{'max-concurrency':4}}},[]),
            ({'node':{'pid':42,'pool':{'max-concurrency':5}}},[{'name':'domestic'}])]:
            inspector = SimpleNamespace(stats=lambda:stats,active_queues=lambda:{'node':queues})
            with self.assertRaises(RuntimeError):
                probe.status(SimpleNamespace(inspect=lambda **k:inspector),42,'node')


if __name__ == '__main__':
    unittest.main()
