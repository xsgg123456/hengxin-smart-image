"""Independent native baselines: shared roots, drift and original-byte backups."""
import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_outon_native as shared

n, r = shared.n, shared.r


class NativeBaselineTests(unittest.TestCase):
    fixture = shared.NativeTests.fixture
    new_file_fixture = shared.NativeTests.new_file_fixture

    def test_preflight_accepts_pinned_native_baseline_different_from_api(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,_ = self.fixture(root)
            for value in data['patch'].values():
                value['baseline'] = 'a'*64
            with patch.object(n,'drop_path',return_value=root/'absent'):
                n.preflight(data)

    def test_distinct_native_roots_each_use_their_own_baseline_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,source = self.fixture(root)
            unit = r.UNITS[1]
            other = root/'other'
            shutil.copytree(root/'native',other)
            name = sorted(r.NATIVE_FILES)[0]
            (other/name).write_text('second native version')
            data['protected']['units'][unit].update(cwd=str(other),source=r.b.tree(other/'app'))
            data['native']['units'][unit]['files'][name] = r.digest(other/name)
            for value in data['patch'].values():
                value['baseline'] = 'a'*64
            with patch.object(n,'drop_path',return_value=root/'absent'):
                n.preflight(data)
            r.private(root/'MIGRATION_VERIFIED',{'manifest':'release','revision':r.REVISION})
            with patch.object(n,'stopped'),patch.object(n.os,'chown',create=True),patch.object(n.r,'run'), \
                 patch.object(n.r,'helper'),patch.object(n,'start'),patch.object(n,'guard'),patch.object(n,'verified'):
                n.install(root,data,source)
            records = json.loads((root/'native-backup.json').read_text())
            self.assertEqual(len(records),2*len(r.NATIVE_FILES))
            for saved_unit in r.UNITS:
                saved_root = Path(data['protected']['units'][saved_unit]['cwd'])
                record = next(v for v in records if v['path']==str(saved_root/name))
                self.assertEqual(r.digest(record['backup']),data['native']['units'][saved_unit]['files'][name])

    def test_unknown_native_drift_is_rejected_before_stop_or_install(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,source = self.fixture(root)
            (root/'native'/sorted(r.NATIVE_FILES)[0]).write_text('unknown native version')
            with patch.object(n,'drop_path',return_value=root/'absent'):
                with self.assertRaisesRegex(RuntimeError,'Native baseline source differs'):
                    n.preflight(data)
            r.private(root/'MIGRATION_VERIFIED',{'manifest':'release','revision':r.REVISION})
            with patch.object(n,'stopped'),self.assertRaisesRegex(RuntimeError,'Native backup mismatch'):
                n.install(root,data,source)
            self.assertFalse((root/'NATIVE_PATCH_STARTED').exists())

    def test_shared_root_conflicting_baselines_fail_preflight_and_install(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,source = self.fixture(root)
            data['native']['units'][r.UNITS[1]]['files'][sorted(r.NATIVE_FILES)[0]] = 'a'*64
            with self.assertRaisesRegex(RuntimeError,'Shared native baseline conflict'):
                n.preflight(data)
            r.private(root/'MIGRATION_VERIFIED',{'manifest':'release','revision':r.REVISION})
            with patch.object(n,'stopped'),self.assertRaisesRegex(RuntimeError,'Shared native baseline conflict'):
                n.install(root,data,source)
            self.assertFalse((root/'native-backup').exists())

    def test_unrelated_service_cannot_share_native_source(self):
        with tempfile.TemporaryDirectory() as folder:
            data,_ = self.fixture(Path(folder))
            data['protected']['units']['other.service'] = dict(data['protected']['units'][r.UNITS[0]])
            with self.assertRaisesRegex(RuntimeError,'shared with unrelated'):
                n.preflight(data)

    def test_preflight_new_helper_requires_absence_even_when_api_has_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data,_,native,name = self.new_file_fixture(root)
            data['patch'][name]['baseline'] = 'a'*64
            with patch.object(n,'drop_path',return_value=root/'absent'):
                n.preflight(data)
                (native/name).mkdir()
                with self.assertRaisesRegex(RuntimeError,'Invalid native baseline file'):
                    n.preflight(data)

