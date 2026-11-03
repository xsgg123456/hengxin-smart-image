"""Backup and isolated restore proofs for the polling release."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_polling_release import load

db = load("polling-database")
r = db.r


class PollingDatabaseTests(unittest.TestCase):
    def test_backup_refuses_live_api(self):
        with patch.object(db.r, 'inspect', return_value={'Id':'old', 'State':{'Running':True}}), \
             patch.object(db.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'stopped'):
                db.backup(Path('unused'), {'oldId':'old'})
            run.assert_not_called()


    def test_restore_checks_all_rows_and_draft_schema_without_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'dump').write_bytes(b'dump')
            (root/'backup').mkdir()
            (root/'backup/schema.json').write_text('{}')
            with patch.object(db.r, 'run', return_value='[{"Image":"postgres-image"}]') as run, \
                 patch.object(db.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)), \
                 patch.object(db.r, 'fingerprints', return_value={'draft':['same']}), \
                 patch.object(db, 'schema', return_value={'drafts':'same'}), \
                 patch.object(db.r, 'sql', return_value=r.REVISION):
                db.restore_test(root, {'manifest':'abc', 'image':'new'}, root/'dump', {'draft':['same']}, {'drafts':'same'})
            self.assertFalse(any('alembic' in call.args for call in run.call_args_list))
            self.assertEqual(run.call_args.args, ('docker', 'rm', '-f', '-v', 'hx-polling-restore-abc'))
            proof = json.loads((root/'restore-proof.json').read_text())
            self.assertFalse(proof['migration'])
            self.assertEqual(proof['revision'], 'overseas_0026')


    def test_draft_schema_difference_rejects_restore_and_cleans_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'dump').write_bytes(b'dump')
            with patch.object(db.r, 'run', return_value='[{"Image":"postgres-image"}]') as run, \
                 patch.object(db.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)), \
                 patch.object(db.r, 'fingerprints', return_value={}), patch.object(db, 'schema', return_value={'wrong':1}):
                with self.assertRaisesRegex(RuntimeError, 'schema differs'):
                    db.restore_test(root, {'manifest':'abc'}, root/'dump', {}, {'right':1})
            self.assertEqual(run.call_args.args, ('docker', 'rm', '-f', '-v', 'hx-polling-restore-abc'))
            self.assertFalse((root/'restore-proof.json').exists())


    def test_backup_evidence_is_bound_to_image_manifest_dump_and_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'backup').mkdir()
            (root/'backup/overseas.dump').write_bytes(b'dump')
            (root/'backup/schema.json').write_text('{}')
            (root/'backup/fingerprints.json').write_text('{}')
            proof = {'manifest':'m', 'image':'new', 'dumpSha256':db.r.digest(root/'backup/overseas.dump'),
                     'schemaSha256':db.r.digest(root/'backup/schema.json'), 'restored':True,
                     'revision':r.REVISION, 'migration':False}
            (root/'restore-proof.json').write_text(json.dumps(proof))
            (root/'backup/COMPLETE').write_text(json.dumps({'dumpSha256':proof['dumpSha256'], 'manifest':'m'}))
            with patch.object(db.r, 'fingerprints', return_value={}), patch.object(db, 'schema', return_value={}):
                db.backup_verified(root, {'manifest':'m', 'image':'new'})
                (root/'backup/overseas.dump').write_bytes(b'drift')
                with self.assertRaisesRegex(RuntimeError, 'proof mismatch'):
                    db.backup_verified(root, {'manifest':'m', 'image':'new'})



if __name__ == "__main__":
    unittest.main()
