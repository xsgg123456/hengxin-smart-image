"""Offline release guard tests. Run: python scripts/release/skill-physical-tests.py."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p = load('skill-physical-runtime')
d = load('skill-physical-deploy')
m = load('skill-physical-maintenance')
m.r = p.r
b = load('skill-physical-backup')


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.before = {'services': {
            'api': {'image': 'old-api', 'volumes': [{'target': p.SKILL_ROOT, 'source': p.SKILL_ROOT, 'read_only': True}]},
            'skill-publisher': {'user': '0:0', 'image': 'old-publisher',
                'environment': {'OVERSEAS_CODEX_EXECUTION_ROOT': '/tmp/unused', 'SAFE': 'keep'},
                'volumes': [{'target': p.SKILL_ROOT, 'source': p.SKILL_ROOT, 'type': 'bind'}]},
            'unrelated': {'image': 'domestic'}}, 'networks': {'private': {'name': 'keep'}}}
        self.images = {'api': 'new-api', 'publisher': 'new-publisher'}

    def merged(self):
        after = copy.deepcopy(self.before)
        overlay = p.overlay(self.before, self.images)
        after['services']['api']['image'] = self.images['api']
        publisher = after['services']['skill-publisher']
        publisher['image'] = self.images['publisher']
        publisher['environment'].update(overlay['services']['skill-publisher']['environment'])
        publisher['volumes'] += overlay['services']['skill-publisher']['volumes']
        return after

    def test_only_publisher_gets_real_history_rw(self):
        after = self.merged()
        p.check_overlay(self.before, after, self.images)
        self.assertNotIn(p.EXECUTION_ROOT, repr(after['services']['api']))
        self.assertEqual(after['services']['skill-publisher']['volumes'][-1]['source'], p.EXECUTION_ROOT)

    def test_api_execution_bind_rejected(self):
        after = self.merged()
        after['services']['api']['volumes'].append({'source': p.EXECUTION_ROOT, 'target': p.EXECUTION_ROOT})
        with self.assertRaisesRegex(RuntimeError, 'Unrelated'):
            p.check_overlay(self.before, after, self.images)

    def test_domestic_or_credentials_change_rejected(self):
        for mutate in (lambda a: a['services']['unrelated'].update(image='oops'),
                       lambda a: a['services']['skill-publisher']['environment'].update(SAFE='oops')):
            after = self.merged()
            mutate(after)
            with self.assertRaisesRegex(RuntimeError, 'Unrelated'):
                p.check_overlay(self.before, after, self.images)

    def test_volume_cannot_replace_actual_history_with_empty_docker_volume(self):
        after = self.merged()
        after['services']['skill-publisher']['volumes'][-1].update(type='volume', source='empty')
        with self.assertRaisesRegex(RuntimeError, 'execution bind'):
            p.check_overlay(self.before, after, self.images)

    def test_existing_execution_mount_is_not_silently_replaced(self):
        self.before['services']['skill-publisher']['volumes'].append({'target': p.EXECUTION_ROOT})
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            p.overlay(self.before, self.images)


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        self.events = []
        self.data = {'manifest': 'hash', 'oldId': 'api', 'oldPublisher': {'id': 'publisher'}}
        self.gate_helper = SimpleNamespace(set_gate=lambda *a: self.events.append('close'),
            require_closed=lambda *a: self.events.append('closed-proof'))
        self.native = SimpleNamespace(stop=lambda *a: self.events.append('native-stop'))
        self.preserve = SimpleNamespace(capture=lambda *a: self.events.append('capture'))
        self.helpers = {'skill-reuse-gate': self.gate_helper, 'sku-native': self.native,
                        'skill-reuse-preserve': self.preserve}

    def tearDown(self):
        self.temp.cleanup()

    def test_gate_drains_before_stopping_and_captures_after_all_writers(self):
        def idle(*args):
            self.events.append('idle')
            return 'node'
        with patch.object(d, 'state', return_value=(self.data, None)), \
             patch.object(d.r, 'inspect', return_value={'Id': 'api'}), \
             patch.object(d, 'inspect', return_value={'Id': 'publisher'}), \
             patch.object(d, 'idle', side_effect=idle), \
             patch.object(d, 'stop_container', side_effect=lambda name: self.events.append(name)), \
             patch.object(d.r, 'helper', side_effect=lambda name: self.helpers[name]), \
             patch.object(d.r, 'worker', side_effect=lambda *a: self.events.append('pause') or {'node': 'node'}), \
             patch.object(d.time, 'sleep'):
            d.gate(self.work)
        self.assertEqual(self.events, ['idle', 'close', 'idle', 'idle', d.r.API, p.PUBLISHER,
                                      'idle', 'pause', 'native-stop', 'capture'])
        self.assertEqual(json.loads((self.work/'gate.json').read_text())['phase'], 'api-stopped-consumer-paused')

    def test_proxy_failure_leaves_services_running(self):
        self.gate_helper.set_gate = lambda *a: (_ for _ in ()).throw(RuntimeError('drain pending'))
        with patch.object(d, 'state', return_value=(self.data, None)), \
             patch.object(d.r, 'inspect', return_value={'Id': 'api'}), \
             patch.object(d, 'inspect', return_value={'Id': 'publisher'}), \
             patch.object(d, 'idle', return_value='node'), \
             patch.object(d.r, 'helper', side_effect=lambda name: self.helpers[name]), \
             patch.object(d, 'stop_container') as stop:
            with self.assertRaisesRegex(RuntimeError, 'drain pending'):
                d.gate(self.work)
            stop.assert_not_called()
        self.assertTrue((self.work/'GATE_STARTED').exists())
        self.assertFalse((self.work/'gate.json').exists())

    def test_stop_is_never_forced(self):
        with patch.object(d.r, 'run') as run, patch.object(d, 'inspect', return_value={'State': {'Running': False}}):
            d.stop_container('publisher')
        run.assert_called_once_with('docker', 'stop', '--time', '-1', 'publisher', timeout=60)

    def test_resumed_release_recovery_requires_fresh_baseline(self):
        (self.work/'RESUMED').write_text('{}')
        with patch.object(d, 'state', return_value=(self.data, None)), patch.object(d, 'stop_container') as stop:
            with self.assertRaisesRegex(RuntimeError, 'fresh preservation'):
                d.recover(self.work)
            stop.assert_not_called()


class PackageTests(unittest.TestCase):
    def test_scope_rejects_shell_and_parent_paths(self):
        for name in ('app/../secret.py', 'app/x.py\nRUN bad', '/app/x.py', 'app/x.py;bad', 'app/x-y.py'):
            self.assertFalse(p.safe_name(name))
        self.assertTrue(p.safe_name('app/overseas/management/skill_objects.py'))

    def test_all_deployment_helpers_are_present_and_compile(self):
        for name in p.HELPERS:
            path = Path(__file__).with_name(name+'.py')
            self.assertTrue(path.is_file(), name)
            compile(path.read_bytes(), str(path), 'exec')


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.owner = 'studio/11111111-1111-1111-1111-111111111111'
        self.directory = [stat.S_IFDIR, 4096, 1, 10, 999, 987, 0o700]
        self.file = [stat.S_IFREG, 10, 1, 11, 999, 987, 0o600]
        self.before = {'tables': {'session': 'unchanged'}, 'files': {
            self.owner: self.directory, self.owner+'/session.json': self.file}}

    def test_additional_owned_skill_history_preserves_originals(self):
        after = copy.deepcopy(self.before)
        after['files'][self.owner][1:3] = [8192, 2]
        after['files'][self.owner+'/skill-history'] = list(self.directory)
        after['files'][self.owner+'/skill-history/'+'a'*64] = list(self.directory)
        after['files'][self.owner+'/skill-history/'+'a'*64+'/example/SKILL.md'] = list(self.file)
        m.history_preserved(self.before, after)

    def test_changed_original_file_rejected_even_with_new_history(self):
        after = copy.deepcopy(self.before)
        after['files'][self.owner+'/session.json'][2] += 1
        with self.assertRaisesRegex(RuntimeError, 'historical file'):
            m.history_preserved(self.before, after)

    def test_other_added_files_or_links_are_rejected(self):
        for name, kind in ((self.owner+'/home/secret', stat.S_IFREG),
                           (self.owner+'/skill-history/'+'a'*64+'/link', stat.S_IFLNK)):
            after = copy.deepcopy(self.before)
            after['files'][name] = [kind, 0, 1, 1, 999, 987, 0o600]
            with self.assertRaises(RuntimeError):
                m.history_preserved(self.before, after)

    def test_conversation_changes_or_deletion_rejected(self):
        for mutate in (lambda a: a['tables'].update(session='changed'),
                       lambda a: a['files'].pop(self.owner+'/session.json')):
            after = copy.deepcopy(self.before)
            mutate(after)
            with self.assertRaises(RuntimeError):
                m.history_preserved(self.before, after)

    def test_maintenance_forbids_old_reader_recovery_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work/'MAINTENANCE_STARTED').write_text('{}')
            with patch.object(d, 'state') as state:
                with self.assertRaisesRegex(RuntimeError, 'schema 2'):
                    d.recover(work)
                state.assert_not_called()


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source, self.work = self.root/'source', self.root/'work'
        (self.source/'版本/空目录').mkdir(parents=True)
        (self.source/'版本/文件').write_bytes(b'\x00same\xff')
        (self.source/'current.json').write_bytes(b'\x00same\xff')
        (self.source/'empty').write_bytes(b'')

    def tearDown(self):
        self.temp.cleanup()

    def backup(self):
        return b.create(self.work, self.source)['indexSha256']

    def test_dedup_utf8_empty_directories_and_roundtrip(self):
        sha = self.backup()
        data = b.verify(self.work, sha)
        self.assertEqual(data['source'], '/var/lib/hengxin-overseas/local-skills')
        self.assertEqual(b.summary(data, sha)['uniqueFiles'], 2)
        self.assertEqual(b.summary(data, sha)['logicalBytes'], 12)
        self.assertEqual(b.summary(data, sha)['payloadBytes'], 6)
        target = self.root/'restored'
        b.restore(self.work, target, sha)
        self.assertEqual(b.snapshot(target), b.snapshot(self.source))
        with self.assertRaisesRegex(RuntimeError, 'empty'):
            b.restore(self.work, target, sha)

    def test_payload_and_index_tampering_rejected(self):
        sha = self.backup()
        payload = next(p for p in (self.work/b.NAME/'payload').iterdir() if p.stat().st_size)
        payload.write_bytes(b'broken')
        with self.assertRaisesRegex(RuntimeError, 'Payload hash'):
            b.restore(self.work, self.root/'restore', sha)
        index = self.work/b.NAME/'index.json'
        index.write_bytes(index.read_bytes()+b' ')
        with self.assertRaisesRegex(RuntimeError, 'Index hash'):
            b.verify(self.work, sha)

    def test_links_and_special_files_rejected(self):
        import os
        os.link(self.source/'empty', self.source/'hardlink')
        with self.assertRaisesRegex(RuntimeError, 'unlinked regular'):
            self.backup()
        (self.source/'hardlink').unlink()
        if hasattr(os, 'mkfifo'):
            os.mkfifo(self.source/'fifo')
            with self.assertRaisesRegex(RuntimeError, 'Special'):
                b.snapshot(self.source)
        with patch.object(Path, 'is_symlink', return_value=True), patch.object(Path, 'lstat',
                return_value=SimpleNamespace(st_mode=stat.S_IFLNK)):
            with self.assertRaisesRegex(RuntimeError, 'Linked'):
                b.safe(self.source)

    def test_posix_symlink_and_ownership_roundtrip(self):
        import os
        if os.name != 'posix':
            return  # The same suite also runs as real root under Linux.
        link = self.source/'symlink'
        link.symlink_to(self.source/'empty')
        with self.assertRaisesRegex(RuntimeError, 'Linked'):
            b.snapshot(self.source)
        link.unlink()
        file = self.source/'版本/文件'
        file.chmod(0o640)
        os.chown(file, 12345, 12346)
        os.utime(file, ns=(123456789000, 123456789000))
        sha = self.backup()
        target = self.root/'restored'
        b.restore(self.work, target, sha)
        self.assertEqual(b.snapshot(target), b.snapshot(self.source))

    def test_path_and_metadata_attacks_rejected(self):
        sha = self.backup()
        data = b.verify(self.work, sha)
        for mutate in (lambda d: d['entries'][1].update(path='../escape'),
                       lambda d: d['entries'][1].update(kind='symlink'),
                       lambda d: d['entries'][1].update(mode=-1),
                       lambda d: d['entries'].append(d['entries'][0])):
            damaged = copy.deepcopy(data)
            mutate(damaged)
            with self.assertRaises(RuntimeError):
                b.valid_index(damaged)
        for target in (b.ROOT, b.ROOT/'nested', b.ROOT.parent, self.work/'restore'):
            with self.assertRaisesRegex(RuntimeError, 'isolated'):
                b.restore(self.work, target, sha)


if __name__ == '__main__':
    unittest.main()
