"""No production calls: graceful-stop order, timeout retention and source recovery evidence."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


n = load('language-native')
d = load('language-deploy')
db = load('language-database')
r = n.r


class NativeTests(unittest.TestCase):
    def fixture(self, root):
        data = {'manifest':'release', 'protected':{'units':{}}, 'patch':{}, 'native':{'units':{}}}
        native = root/'native'
        source = root/'source'
        for name in r.NATIVE_FILES:
            for base, contents in ((native,'old code'),(source/'api','new code')):
                path = base/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(contents)
            data['patch'][name] = {'baseline':r.digest(native/name),'sha256':r.digest(source/'api'/name)}
        for index,unit in enumerate(r.UNITS):
            data['native']['units'][unit] = {'files':{name:r.digest(native/name) for name in r.NATIVE_FILES}}
            data['protected']['units'][unit] = {'pid':10+index,'cwd':str(native),'files':{},
                                              'source':r.b.tree(native/'app')}
        r.private(root/'gate.json',{'node':'worker','manifest':'release'})
        return data, source

    def test_busy_consumer_cannot_create_stop_override(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,_ = self.fixture(root)
            with patch.object(n.r,'worker',side_effect=RuntimeError('busy')), patch.object(n.r,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'busy'):
                    n.stop(root,data)
            run.assert_not_called()
            self.assertFalse((root/'NATIVE_STOP_STARTED').exists())

    def test_stop_disables_force_kill_before_stopping_outbox_then_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,_ = self.fixture(root)
            calls = []
            def run(*args,**kwargs):
                calls.append(args)
                if 'SendSIGKILL' in args:
                    return 'no'
                if 'TimeoutStopUSec' in args:
                    return 'infinity'
                if 'ActiveState' in args:
                    return 'inactive'
                return '0'
            with patch.object(n,'drop_path',side_effect=lambda u:root/(u+'.d')/'stop.conf'), \
                 patch.object(n.r,'worker'), patch.object(n.r,'run',side_effect=run):
                n.stop(root,data)
            stops = [c for c in calls if c[1]=='stop']
            self.assertEqual(stops,[('systemctl','stop','--no-block',u) for u in reversed(r.UNITS)])
            last_check = max(i for i,c in enumerate(calls) if 'TimeoutStopUSec' in c)
            first_stop = min(i for i,c in enumerate(calls) if c[1]=='stop')
            self.assertLess(last_check,first_stop)
            self.assertTrue((root/'NATIVE_STOPPED').exists())

    def test_stop_timeout_keeps_protection_and_never_escalates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,_ = self.fixture(root)
            def run(*args,**kwargs):
                if 'SendSIGKILL' in args:
                    return 'no'
                if 'TimeoutStopUSec' in args:
                    return 'infinity'
                return 'deactivating'
            with patch.object(n,'drop_path',side_effect=lambda u:root/(u+'.d')/'stop.conf'), \
                 patch.object(n.r,'worker'),patch.object(n.r,'run',side_effect=run) as host, \
                 patch.object(n.time,'monotonic',side_effect=[0,61]):
                with self.assertRaisesRegex(RuntimeError,'pending'):
                    n.stop(root,data)
            self.assertTrue(all((root/(u+'.d')/'stop.conf').read_text()==n.DROP_CONTENT for u in r.UNITS))
            self.assertFalse((root/'NATIVE_STOPPED').exists())
            self.assertFalse(any('kill' in c.args for c in host.call_args_list))

    def test_partial_install_retains_original_backup_and_cannot_be_blindly_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,source = self.fixture(root)
            r.private(root/'MIGRATION_VERIFIED',{'manifest':'release','revision':r.REVISION})
            replace = n.os.replace
            def fail_source(src,dest):
                if str(dest).endswith('.py'):
                    raise OSError('disk failure')
                return replace(src,dest)
            with patch.object(n,'stopped'),patch.object(n.os,'chown',create=True), \
                 patch.object(n.os,'replace',side_effect=fail_source):
                with self.assertRaises(OSError):
                    n.install(root,data,source)
            records = json.loads((root/'native-backup.json').read_text())
            self.assertEqual(len(records),len(r.NATIVE_FILES))
            self.assertTrue(all(r.digest(v['backup'])==v['sha256'] for v in records))
            self.assertTrue((root/'NATIVE_PATCH_STARTED').exists())
            self.assertFalse((root/'NATIVE_INSTALLED').exists())
            with self.assertRaisesRegex(RuntimeError,'partial native patch'):
                n.install(root,data,source)

    def test_unrelated_native_source_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,_ = self.fixture(root)
            other = root/'native/app/unrelated.py'
            other.write_text('unexpected')
            with patch.object(n,'pid',side_effect=[10]),patch.object(n,'drop_path',return_value=root/'absent'):
                with self.assertRaisesRegex(RuntimeError,'Native source drift'):
                    n.guard(root,data)

    def new_file_fixture(self, root):
        data, source = self.fixture(root)
        name = 'app/overseas/archives/snapshot.py'
        native = Path(data['protected']['units'][r.UNITS[0]]['cwd'])
        (native/name).unlink()
        data['patch'][name]['baseline'] = None
        for saved in data['protected']['units'].values():
            saved['source'] = r.b.tree(native/'app')
        for saved in data['native']['units'].values():
            saved['files'][name] = None
        r.private(root/'MIGRATION_VERIFIED',{'manifest':'release','revision':r.REVISION})
        return data, source, native, name

    def test_new_native_helper_is_installed_with_explicit_absence_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data, source, native, name = self.new_file_fixture(root)
            with patch.object(n,'stopped'),patch.object(n.os,'chown',create=True),patch.object(n.r,'run'), \
                 patch.object(n.r,'helper'),patch.object(n,'start'),patch.object(n,'guard'),patch.object(n,'verified'):
                n.install(root,data,source)
            self.assertEqual(r.digest(native/name),data['patch'][name]['sha256'])
            records = json.loads((root/'native-backup.json').read_text())
            added = next(v for v in records if v['path'] == str(native/name))
            self.assertEqual(added,{'path':str(native/name),'backup':None,'sha256':None})
            self.assertTrue(all(r.digest(v['backup'])==v['sha256'] for v in records if v['backup']))

    def test_new_native_file_collision_is_rejected_before_patch_started(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data, source, native, name = self.new_file_fixture(root)
            (native/name).write_text('unexpected')
            with patch.object(n,'stopped'),self.assertRaisesRegex(RuntimeError,'Unexpected new native'):
                n.install(root,data,source)
            self.assertFalse((root/'NATIVE_PATCH_STARTED').exists())
            self.assertEqual((native/name).read_text(),'unexpected')

    def test_partial_guard_accepts_absent_new_file_then_exact_pinned_file_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data, source, native, name = self.new_file_fixture(root)
            r.private(root/'NATIVE_PATCH_STARTED',{'manifest':'release'})
            with patch.object(n,'pid',side_effect=lambda u:data['protected']['units'][u]['pid']), \
                 patch.object(n,'drop_path',return_value=root/'absent'):
                n.guard(root,data)
                (native/name).write_bytes((source/'api'/name).read_bytes())
                n.guard(root,data)
                (native/name).write_text('corrupted')
                with self.assertRaisesRegex(RuntimeError,'Native patch drift'):
                    n.guard(root,data)

    def test_completed_install_guard_requires_new_helper_present(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data, _, _, _ = self.new_file_fixture(root)
            r.private(root/'NATIVE_PATCH_STARTED',{'manifest':'release'})
            r.private(root/'NATIVE_INSTALLED',{'manifest':'release'})
            with patch.object(n,'pid',side_effect=lambda u:data['protected']['units'][u]['pid']), \
                 patch.object(n,'drop_path',return_value=root/'absent'):
                with self.assertRaisesRegex(RuntimeError,'Native installation incomplete'):
                    n.guard(root,data)

    def test_native_restart_never_installs_workflow_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,source = self.fixture(root)
            r.private(root/'MIGRATION_VERIFIED',{'manifest':'release','revision':r.REVISION})
            events = []
            def configure(work, saved):
                self.assertTrue((root/'NATIVE_INSTALLED').exists())
                native = Path(data['protected']['units'][r.UNITS[0]]['cwd'])
                self.assertTrue(all(r.digest(native/name) == data['patch'][name]['sha256'] for name in r.NATIVE_FILES))
                events.append('workflow')
            with patch.object(n,'stopped'),patch.object(n.os,'chown',create=True),patch.object(n.r,'run'), \
                 patch.object(n.r,'helper',return_value=SimpleNamespace(install=configure)), \
                 patch.object(n,'start',side_effect=lambda *args:events.append('restart')), \
                 patch.object(n,'guard'),patch.object(n,'verified'):
                n.install(root,data,source)
            self.assertEqual(events,['restart'])

    def test_verified_native_rejects_changed_workflow_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,_ = self.fixture(root)
            data['environment'] = {'native':{unit:'original' for unit in r.UNITS}}
            r.private(root/'NATIVE_INSTALLED',{'manifest':'release'})
            r.private(root/'NATIVE_VERIFIED',{'manifest':'release','pids':{unit:10 for unit in r.UNITS}})
            with patch.object(n.r,'native_environment',return_value='changed'):
                with self.assertRaisesRegex(RuntimeError,'environment changed'):
                    n.verified(root,data)

    def test_migration_started_blocks_old_api_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'MIGRATION_STARTED').write_text('started')
            with patch.object(d,'state',return_value=({},None)),patch.object(d.r,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'forward recovery'):
                    d.recover_before_switch(root)
            run.assert_not_called()

    def test_failed_restore_proof_cannot_start_production_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(db,'closed_gate'),patch.object(db,'backup_verified',side_effect=RuntimeError('bad dump')), \
                 patch.object(db.r.a,'compose') as compose:
                with self.assertRaisesRegex(RuntimeError,'bad dump'):
                    db.migrate(root,{})
            compose.assert_not_called()
            self.assertFalse((root/'MIGRATION_STARTED').exists())

    def test_unknown_stop_override_is_not_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root/'stop.conf'
            target.write_text('foreign configuration')
            with patch.object(n,'drop_path',return_value=target),patch.object(n.r,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'drift'):
                    n.remove_protection()
            self.assertTrue(target.exists())
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
