"""Recover through real sku state/guard and real native stop/restore after interruptions."""
import json
from contextlib import ExitStack
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_studio_batch_recovery import load

adapter = load('studio-batch-runtime')
r = adapter.r
recovery = load('studio-batch-recovery')


class ReentryTests(unittest.TestCase):
    def test_recovery_stop_timeout_retains_protection_without_force_kill(self):
        state = r.helper('studio-batch-recovery-state')
        native = r.helper('sku-native')
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            r.private(work/'gate.json',{'node':'node'})
            def run(*args,**kwargs):
                return 'no' if 'SendSIGKILL' in args else 'infinity'
            with patch.object(native,'pid',return_value=42),patch.object(r,'worker'), \
                patch.object(native,'drop_path',side_effect=lambda u:work/u/'guard.conf'), \
                patch.object(r,'run',side_effect=run) as commands, \
                patch.object(state.time,'monotonic',side_effect=[0,1,61]):
                with self.assertRaisesRegex(RuntimeError,'pending'):
                    state.stop(work,{'manifest':'m'},r,native)
                self.assertTrue(all(native.drop_path(u).read_text() == native.DROP_CONTENT for u in r.UNITS))
                self.assertFalse(any('kill' in call.args or 'start' in call.args for call in commands.call_args_list))

    def exercise(self, fault):
        native, restore, sku = (r.helper(name) for name in ('sku-native','studio-batch-native','sku-deploy'))
        recovery_state = r.helper('studio-batch-recovery-state')
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            root, source = work/'native',work/'source'
            source.mkdir()
            (source/'release.json').write_text('manifest')
            name = next(iter(r.NATIVE_FILES))
            target = root/name
            target.parent.mkdir(parents=True)
            target.write_text('old source')
            oldhash = r.digest(target)
            baseline = r.b.tree(root/'app')
            saved = work/'old.py'
            saved.write_text('old source')
            target.write_text('new source')
            newhash = r.digest(target)
            (work/'api-overlay.json').write_text('overlay')
            data = dict(manifest=r.digest(source/'release.json'),source=str(source),image='new',oldImage='old',
                oldId='id',patch={name:{'baseline':oldhash,'sha256':newhash}},
                native={'units':{u:{'files':{name:oldhash}} for u in r.UNITS}},
                compose={'files':{}},overlayHash=r.digest(work/'api-overlay.json'),
                environment={'api':'env','native':{u:'env' for u in r.UNITS}},
                protected={'units':{u:{'pid':10+i,'cwd':str(root),'files':{},'source':baseline}
                    for i,u in enumerate(r.UNITS)},'skills':{},'containers':{}})
            for marker in ('NATIVE_STOP_STARTED','NATIVE_START_STARTED','NATIVE_PATCH_STARTED','NATIVE_INSTALLED'):
                r.private(work/marker,{'manifest':data['manifest']})
            r.private(work/'GATE_STARTED',{'node':'node'})
            r.private(work/'gate.json',{'node':'node'})
            r.private(work/'INSTALL_TESTS_PASSED',{'manifest':data['manifest'],'image':'new'})
            pids = {u:20+i for i,u in enumerate(r.UNITS)}
            r.private(work/'NATIVE_VERIFIED',{'manifest':data['manifest'],'pids':pids.copy()})
            r.private(work/'native-backup.json',[dict(path=str(target),backup=str(saved),sha256=oldhash,name=name)])
            r.private(work/'prepared.json',data)
            events, triggered = [], [False]
            api_running = [False]
            def run(*args,**kwargs):
                if args[0] == 'docker':
                    api_running[0] = args[1] == 'start'
                    events.append('api-'+args[1])
                    return ''
                if args[1] == 'daemon-reload':
                    return ''
                unit = args[-1] if args[1] in ('stop','start') else args[2]
                if args[1] == 'stop':
                    if fault == 'stop' and unit == r.UNITS[0] and not triggered[0]:
                        triggered[0] = True
                        raise OSError('interrupted stop')
                    pids[unit] = 0
                    events.append('stopped-'+unit)
                elif args[1] == 'start':
                    pids[unit] = 30+r.UNITS.index(unit)
                elif args[1] == 'is-active':
                    return 'active'
                elif 'ActiveState' in args:
                    return 'active' if pids[unit] else 'inactive'
                elif 'Job' in args:
                    return '0'
                elif 'SendSIGKILL' in args:
                    return 'no'
                elif 'TimeoutStopUSec' in args:
                    return 'infinity'
                return ''
            original_copy = restore.shutil.copy2
            def copy(*args,**kwargs):
                if fault == 'partial' and not triggered[0]:
                    triggered[0] = True
                    Path(args[1]).write_bytes(b'old')
                    raise OSError('interrupted partial copy')
                result = original_copy(*args,**kwargs)
                if fault == 'copy' and not triggered[0]:
                    triggered[0] = True
                    raise OSError('interrupted copy')
                return result
            original_atomic = restore.os.replace
            def atomic(src,dst):
                if fault == 'atomic' and Path(dst) == target and not triggered[0]:
                    triggered[0] = True
                    raise OSError('interrupted before atomic replace')
                return original_atomic(src,dst)
            original_replace = Path.replace
            def replace(path,*args,**kwargs):
                if fault == 'retire' and path.name == 'NATIVE_INSTALLED' and not triggered[0]:
                    triggered[0] = True
                    raise OSError('interrupted retirement')
                return original_replace(path,*args,**kwargs)
            original_stat, original_tree = Path.stat,r.b.tree
            def stat(path,*args,**kwargs):
                return SimpleNamespace(st_uid=999) if path.as_posix().startswith('/proc/') else original_stat(path,*args,**kwargs)
            def tree(path):
                return {} if str(path).endswith('local-skills') else original_tree(path)
            helpers = {'sku-native':native,'studio-batch-native':restore,'studio-batch-recovery-state':recovery_state,
                'skill-folders-gateway':SimpleNamespace(refresh=lambda *a:events.append('gateway'))}
            live = lambda:{'Id':'id','Image':'old','State':{'Running':api_running[0]},'Config':{'Env':[]}}
            patches = (patch.object(r,'helper',side_effect=lambda n:helpers[n]), \
                patch.object(r,'run',side_effect=run),patch.object(native,'pid',side_effect=lambda u,**k:pids[u]), \
                patch.object(native,'drop_path',side_effect=lambda u:work/'drops'/u/'guard.conf'), \
                patch.object(r,'worker',return_value={'node':'node','paused':True}), \
                patch.object(r,'worker_probe',return_value={'node':'node'}),patch.object(r,'inspect',side_effect=live), \
                patch.object(r,'verify_package',return_value={'native':data['native'],'api':{'files':data['patch']}}), \
                patch.object(r,'hashes',side_effect=lambda image:{name:oldhash if image == 'old' else newhash}), \
                patch.object(r.a,'compose',return_value='{}'),patch.object(r.a,'check_live_config'), \
                patch.object(r,'environment_hash',return_value='env'),patch.object(r,'native_environment',return_value='env'), \
                patch.object(r.b,'tree',side_effect=tree),patch.object(native.os,'readlink',return_value=str(root)), \
                patch.object(Path,'stat',stat),patch.object(Path,'replace',replace), \
                patch.object(restore.os,'chown',create=True),patch.object(restore.os,'replace',side_effect=atomic), \
                patch.object(restore.shutil,'copy2',side_effect=copy))
            with ExitStack() as stack:
                for item in patches:
                    stack.enter_context(item)
                def state(work,**kwargs):
                    return sku.state(work,tested=True)
                with self.assertRaisesRegex(OSError,'interrupted'):
                    recovery.recover(work,r,state,lambda:None,True)
                self.assertFalse(api_running[0])
                if fault in ('partial','copy','atomic'):
                    self.assertEqual(target.read_text(),'new source')
                # The unmodified legacy guard rejected both these durable partial states.
                sku.state(work,tested=True)
                proof = json.loads((work/'NATIVE_RECOVERY.json').read_text())
                self.assertEqual(proof['phase'],'stopping' if fault == 'stop' else 'restoring')
                # Do not relax identity or unrelated source protection to obtain reentry.
                previous = pids[r.UNITS[0]]
                pids[r.UNITS[0]] = 999
                with self.assertRaisesRegex(RuntimeError,'Unexpected native restart'):
                    sku.state(work,tested=True)
                pids[r.UNITS[0]] = previous
                unrelated = root/'app/unrelated.py'
                unrelated.write_text('foreign bytes')
                with self.assertRaisesRegex(RuntimeError,'Native source drift'):
                    sku.state(work,tested=True)
                unrelated.unlink()
                recovery.recover(work,r,state,lambda:None,True)
                self.assertEqual(target.read_text(),'old source')
                self.assertTrue(api_running[0])
                self.assertTrue((work/'RECOVERED_BEFORE_SWITCH').exists())
                self.assertFalse((work/'NATIVE_RECOVERY.json').exists())
                self.assertEqual(list(root.glob('.studio-batch-restore-*')),[])
                sku.state(work,tested=True)

    def test_outbox_stopped_worker_alive_reenters_with_same_protection(self):
        self.exercise('stop')

    def test_complete_temporary_copy_interruption_reenters(self):
        self.exercise('copy')

    def test_partial_marker_retirement_still_resumes_restore(self):
        self.exercise('retire')

    def test_partial_backup_copy_keeps_live_file_intact_and_reenters(self):
        self.exercise('partial')

    def test_interrupted_atomic_replace_reenters_without_source_drift(self):
        self.exercise('atomic')


if __name__ == '__main__':
    unittest.main()
