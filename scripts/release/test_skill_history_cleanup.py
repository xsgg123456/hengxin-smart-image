"""Real temporary files prove backup, scope, rollback and non-Skill preservation."""
import importlib.util
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('history_files',Path(__file__).with_name('skill-history-files.py'))
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


class HistoryCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'production'
        self.work = Path(self.temp.name)/'maintenance'
        self.root.mkdir(); self.work.mkdir()
        self.conv = str(uuid4())
        self.names = [f'{self.conv}/rounds/{uuid4()}/skills/demo' for _ in range(3)]
        for name in self.names:
            package = self.root/name
            package.mkdir(parents=True)
            (package/'SKILL.md').write_bytes(b'original skill')
            (package/'font.bin').write_bytes(b'font bytes\x00')
        self.history = self.root/self.conv/'history.jsonl'
        self.history.write_bytes(b'full unabridged context\n')
        self.group = dict(key='a'*64,conversation=self.conv,keep=self.names[0],drop=self.names[1:],
                          entries=f.inventory(self.root/self.names[0])[0])

    def test_backup_roundtrip_preserves_all_skill_bytes(self):
        archive = self.work/'backup.tar.gz'
        plan = dict(groups=[self.group])
        f.backup(self.root,plan,archive)
        f.verify_backup(plan,archive)
        restored = self.work/'restored'
        restored.mkdir()
        with tarfile.open(archive) as bundle:
            for member in bundle:
                if member.isfile():
                    path = restored/Path(member.name).name
                    path.write_bytes(bundle.extractfile(member).read())
                    path.chmod(member.mode)
        self.assertEqual(f.inventory(restored)[0],self.group['entries'])

    @unittest.skipUnless(os.name=='posix','Directory fsync on Linux')
    def test_receipt_fsyncs_file_then_parent_directory(self):
        import stat
        kinds = []
        original = os.fsync
        def synced(fd):
            kinds.append(stat.S_IFMT(os.fstat(fd).st_mode))
            original(fd)
        with patch.object(f.os,'fsync',side_effect=synced):
            f.save(self.work/'receipt.json',{'ok':True})
        self.assertEqual(kinds,[stat.S_IFREG,stat.S_IFDIR])

    @unittest.skipUnless(os.name=='posix','Production link-safe rmtree requires POSIX')
    def test_remove_only_duplicate_packages_preserves_history_and_keep(self):
        info = self.history.stat()
        count = f.move_checked(self.root,self.work,self.conv,[self.group],lambda:'db-original')
        self.assertGreater(count,0)
        self.assertEqual(self.history.read_bytes(),b'full unabridged context\n')
        self.assertEqual((info.st_ino,info.st_mtime_ns),(self.history.stat().st_ino,self.history.stat().st_mtime_ns))
        self.assertEqual(f.inventory(self.root/self.names[0])[0],self.group['entries'])
        self.assertTrue(all(not (self.root/n).exists() for n in self.names[1:]))
        self.assertTrue(all((self.root/n).parent.exists() for n in self.names))

    def test_database_drift_restores_every_moved_package(self):
        values = iter(['before','after'])
        with self.assertRaisesRegex(ValueError,'records changed'):
            f.move_checked(self.root,self.work,self.conv,[self.group],lambda:next(values))
        for name in self.names:
            self.assertEqual(f.inventory(self.root/name)[0],self.group['entries'])

    def test_receipt_write_failure_restores_every_moved_package(self):
        original = f.save
        def save(path, value):
            if path.name.startswith('verified-'):
                raise OSError(28,'No space left on device')
            return original(path,value)
        with patch.object(f,'save',side_effect=save),self.assertRaises(OSError):
            f.move_checked(self.root,self.work,self.conv,[self.group],lambda:'same')
        for name in self.names:
            self.assertEqual(f.inventory(self.root/name)[0],self.group['entries'])

    def test_persistent_sync_failure_still_restores_all_paths(self):
        original = f.sync_directory
        def sync(path):
            if (self.work/('verified-'+self.conv+'.json')).exists():
                raise OSError(5,'Persistent sync failure')
            return original(path)
        with patch.object(f,'sync_directory',side_effect=sync),self.assertRaises(RuntimeError):
            f.move_checked(self.root,self.work,self.conv,[self.group],lambda:'same')
        for name in self.names:
            self.assertEqual(f.inventory(self.root/name)[0],self.group['entries'])

    def test_changed_copy_is_rejected_without_removing_anything(self):
        (self.root/self.names[2]/'font.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Duplicate drift'):
            f.move_checked(self.root,self.work,self.conv,[self.group],lambda:'same')
        self.assertTrue(all((self.root/n).exists() for n in self.names))

    @unittest.skipUnless(os.name=='posix','POSIX directory permissions')
    def test_root_permission_drift_is_not_a_duplicate(self):
        package = self.root/self.names[1]
        package.chmod(0o700)
        with self.assertRaisesRegex(ValueError,'Duplicate drift'):
            f.move_checked(self.root,self.work,self.conv,[self.group],lambda:'same')
        self.assertTrue(all((self.root/n).exists() for n in self.names))

    @unittest.skipUnless(os.name=='posix' and getattr(os,'geteuid',lambda:-1)()==0,'Linux root chown')
    def test_root_owner_drift_is_not_a_duplicate(self):
        package = self.root/self.names[1]
        os.chown(package,65534,65534)
        with self.assertRaisesRegex(ValueError,'Duplicate drift'):
            f.move_checked(self.root,self.work,self.conv,[self.group],lambda:'same')
        self.assertTrue(all((self.root/n).exists() for n in self.names))

    def test_cross_conversation_and_wrong_targets_rejected(self):
        other = str(uuid4())+'/rounds/'+str(uuid4())+'/skills/demo'
        self.group['drop']=[other]
        with self.assertRaisesRegex(ValueError,'Cross-conversation'):
            f.move_checked(self.root,self.work,self.conv,[self.group],lambda:'same')
        for relative in ('../home','/'+self.names[0],self.conv+'/home'):
            with self.assertRaises(ValueError): f.target(self.root,relative)

    @unittest.skipUnless(os.name=='posix','POSIX links')
    def test_links_refused(self):
        path = self.root/self.names[1]/'SKILL.md'
        path.unlink()
        path.symlink_to(self.root/self.names[0]/'SKILL.md')
        with self.assertRaisesRegex(ValueError,'Linked path'): f.inventory(path.parent)


if __name__=='__main__': unittest.main()
