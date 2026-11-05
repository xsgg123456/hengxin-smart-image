"""Filesystem fault tests for native replacement and restoration; no production I/O."""
import importlib.util
import json
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


n = load('studio-batch-native')
r = n.r


class NativeTests(unittest.TestCase):
    def fixture(self, work):
        root, source = work/'native', work/'source'
        name = next(iter(r.NATIVE_FILES))
        for base, text in ((root, 'OLD = True\n'), (source/'api', 'NEW = True\n')):
            path = base/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        baseline = r.digest(root/name)
        data = {'manifest':'manifest', 'patch':{name:{'sha256':r.digest(source/'api'/name)}},
                'native':{'units':{u:{'files':{name:baseline}} for u in r.UNITS}},
                'protected':{'units':{u:{'cwd':str(root)} for u in r.UNITS}},
                'environment':{'native':{u:'envhash' for u in r.UNITS}}}
        native = SimpleNamespace(stopped=Mock(), safe=lambda path:path,
            baseline_roots=lambda data:{str(root):{name:baseline}},
            start=Mock(), guard=Mock(), verified=Mock())
        database = SimpleNamespace(backup_verified=Mock())
        helper = lambda module: native if module=='sku-native' else database
        return data, source, root/name, native, database, helper

    def test_failed_replace_keeps_original_backup_and_repair_reuses_it(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            data, source, target, native, database, helper = self.fixture(work)
            replace = n.os.replace
            def failing_replace(src, dst):
                if str(dst).endswith('.py'):
                    raise OSError('disk failure')
                return replace(src, dst)
            with patch.object(r, 'helper', side_effect=helper), patch.object(n.os, 'chown', create=True), \
                 patch.object(n.os, 'replace', side_effect=failing_replace), patch.object(r, 'run'), \
                 patch.object(n, 'semantic_probe'):
                with self.assertRaisesRegex(OSError, 'disk failure'):
                    n.install(work, data, source)
            self.assertEqual(target.read_text(), 'OLD = True\n')
            records = (work/'native-backup.json').read_bytes()
            self.assertTrue((work/'NATIVE_PATCH_STARTED').exists())
            native.start.assert_not_called()
            # An incomplete temporary file is retained for inspection, never blindly overwritten.
            temporary = target.with_name(target.name+'.studio-batch-new')
            self.assertTrue(temporary.exists())
            temporary.unlink()
            with patch.object(r, 'helper', side_effect=helper), patch.object(n.os, 'chown', create=True), \
                 patch.object(r, 'run'), patch.object(n, 'semantic_probe') as probe:
                n.install(work, data, source)
            self.assertEqual((work/'native-backup.json').read_bytes(), records)
            self.assertEqual(target.read_text(), 'NEW = True\n')
            probe.assert_called_once_with(data)
            native.start.assert_called_once_with(work, data)
            database.backup_verified.assert_called()

    def test_restore_reinstates_bytes_before_start_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            data, source, target, native, _, helper = self.fixture(work)
            with patch.object(r, 'helper', side_effect=helper), patch.object(n.os, 'chown', create=True), \
                 patch.object(r, 'run'), patch.object(n, 'semantic_probe'):
                n.install(work, data, source)
            native.start.reset_mock()
            def restart(*args, **kwargs):
                self.assertEqual(target.read_text(), 'OLD = True\n')
                self.assertFalse((work/'NATIVE_INSTALLED').exists())
            native.start.side_effect = restart
            with patch.object(r, 'helper', side_effect=helper), patch.object(n.os, 'chown', create=True), \
                 patch.object(r, 'native_environment', return_value='envhash'):
                n.restore(work, data)
            native.start.assert_called_once_with(work, data, recovery=True)
            self.assertTrue((work/'NATIVE_PATCH_STARTED_RESTORED').exists())
            self.assertTrue((work/'native-backup.json').exists())

    def test_corrupt_backup_never_replaces_native_source(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            data, source, target, native, _, helper = self.fixture(work)
            with patch.object(r, 'helper', side_effect=helper), patch.object(n.os, 'chown', create=True), \
                 patch.object(r, 'run'), patch.object(n, 'semantic_probe'):
                n.install(work, data, source)
            records = json.loads((work/'native-backup.json').read_text())
            Path(records[0]['backup']).write_text('tampered')
            native.start.reset_mock()
            with patch.object(r, 'helper', side_effect=helper):
                with self.assertRaisesRegex(RuntimeError, 'backup drift'):
                    n.restore(work, data)
            self.assertEqual(target.read_text(), 'NEW = True\n')
            native.start.assert_not_called()

    def test_actual_installed_path_and_service_identity_are_used(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            data, _, target, _, _, helper = self.fixture(work)
            with patch.object(r, 'helper', side_effect=helper), \
                 patch.object(r, 'run', return_value='NATIVE_REFERENCE_BINDING_OK') as run:
                n.semantic_probe(data)
            call = run.call_args.args
            self.assertEqual(call[:4], ('runuser','-u','hengxin-overseas','--'))
            self.assertIn(repr(str(target)), call[-1])
            self.assertIn('full purpose', call[-1])
            self.assertIn('reference detail', call[-1])
            self.assertEqual(run.call_count, 1)  # Shared source root is inspected once.


if __name__ == '__main__':
    unittest.main()
