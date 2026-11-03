"""Packaging gates: reviewed source, fresh build, privacy checks and racing output."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('archive_package', HERE/'archive-package.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ArchivePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.commit = 'a'*40
        self.status = {'approved':True,'currentId':'b'*64}
        self.dirty = False
        self.source = {}
        for name in ['hengxin-smart-image/frontend/package.json', *['scripts/release/'+n+'.py' for n in p.r.HELPERS]]:
            raw = b'{"version":"0.2.62"}' if name.endswith('package.json') else (HERE/Path(name).name).read_bytes()
            path = self.repo/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(raw)
            self.source[name] = raw
        real_common = p.r.helper('package-delivery')
        self.common = SimpleNamespace(git=self.git,reviewed_status=Mock(return_value=self.status),
                                      normalized=real_common.normalized,privacy_check=Mock(wraps=real_common.privacy_check))
        self.assets = {'frontend/dist/index.html':b'<script src="/assets/new-hash.js"></script>',
                       'frontend/dist/assets/new-hash.js':b'new'}
        self.collect = Mock(side_effect=lambda _:dict(self.assets))
        self.original_helper = p.r.helper
        def helper(name):
            if name == 'package-delivery': return self.common
            if name == 'package-overseas': return SimpleNamespace(collect_assets=self.collect)
            return self.original_helper(name)
        self.patch_helper = patch.object(p.r,'helper',side_effect=helper)
        self.patch_helper.start()
        self.addCleanup(self.patch_helper.stop)
        self.build = patch.object(p.subprocess,'run')
        self.build_call = self.build.start()
        self.addCleanup(self.build.stop)

    def git(self, repo, *args):
        if args[0] == 'diff': return b'changed' if self.dirty else b''
        if args[0] == 'ls-files': return b''
        if args[0] == 'rev-parse': return self.commit.encode()
        if args[0] == 'show': return self.source[args[1].split(':',1)[1]]
        self.fail(args)

    def test_success_rebuilds_and_ships_only_two_self_contained_helpers(self):
        audit = p.build(self.repo)
        self.assertEqual(audit['privacy'],'PASS')
        self.build_call.assert_called_once()
        self.assertEqual(self.build_call.call_args.args[0][-3:],['exec','vite','build'])
        self.assertEqual(self.common.privacy_check.call_count,3)
        self.assertEqual(self.collect.call_count,2)
        self.assertTrue((self.repo/'output/release'/audit['release']/'release.tar.gz').is_file())

    def test_dirty_source_rejected_before_build(self):
        self.dirty = True
        with self.assertRaisesRegex(RuntimeError,'Commit'):
            p.build(self.repo)
        self.build_call.assert_not_called()

    def test_missing_approval_rejected_before_build(self):
        self.common.reviewed_status.side_effect = ValueError('snapshot not approved')
        with self.assertRaisesRegex(ValueError,'approved'):
            p.build(self.repo)
        self.build_call.assert_not_called()

    def test_source_changes_during_build_rejected(self):
        self.common.reviewed_status.side_effect = [self.status,{'currentId':'c'*64}]
        with self.assertRaisesRegex(RuntimeError,'Snapshot changed'):
            p.build(self.repo)
        self.assertFalse((self.repo/'output/release').exists())

    def test_dist_changes_during_packaging_rejected(self):
        self.collect.side_effect = [self.assets,{**self.assets,'frontend/dist/new.js':b'changed'}]
        with self.assertRaisesRegex(RuntimeError,'Frontend changed'):
            p.build(self.repo)
        self.assertFalse((self.repo/'output/release').exists())

    def test_privacy_failure_stops_artifact(self):
        self.common.privacy_check.side_effect = ValueError('Privacy failure')
        with self.assertRaisesRegex(ValueError,'Privacy'):
            p.build(self.repo)
        self.assertFalse((self.repo/'output/release').exists())


if __name__ == '__main__':
    unittest.main()
