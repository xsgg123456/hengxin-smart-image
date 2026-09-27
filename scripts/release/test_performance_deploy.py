"""Execute the deployment controller against simulated production failures."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deploy', Path(__file__).with_name('performance-deploy.py'))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class RecoveryTests(unittest.TestCase):
    def exercise(self, failure):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release = 'performance-20260927-abcdef0'
            work = root / 'hengxin-releases' / release
            source = work / 'src'
            source.mkdir(parents=True)
            (work / 'INSTALL_TEST_IMAGE_ID').write_text('image-id')
            (source / 'release.json').write_text(json.dumps(dict(
                release=release, migration='0019', frontendVersion='0.2.8')))
            helper = source / 'scripts/release/image-inputs-worker.py'
            helper.parent.mkdir(parents=True)
            helper.write_text('# test helper')
            native = root / 'app/backend'
            (native / 'app').mkdir(parents=True)
            (native / 'app/version.py').write_text('old')
            backup_root = root / 'hengxin-backups'
            backup_root.mkdir()
            events, state = [], {'schema': '0017', 'paused': False}

            def sql(query):
                events.append(('sql', query))
                if 'version_num' in query: return state['schema']
                if 'SELECT paused' in query: return 't' if state['paused'] else 'f'
                if 'SELECT enabled' in query: return 'f'
                if 'SELECT count' in query: return '0'
                if 'SET paused=' in query: state['paused'] = 'paused=true' in query
                return ''

            def compose(paths, *args, **kwargs):
                events.append(('compose', tuple(paths), args))
                if 'migrate' in args: state['schema'] = '0019'
                if failure == 'rollback' and paths == ['old'] and args[0] == 'up':
                    raise RuntimeError('rollback failed')
                return ''

            def run(*args, **kwargs):
                events.append(('run', args))
                if args[:3] == ('docker', 'image', 'inspect'): return 'image-id'
                if args[:3] == ('uv', 'pip', 'check'): raise RuntimeError('dependency verification failed')
                if args[:2] == ('systemctl', 'show'): return 'inactive'
                if args[:2] == ('cp', '-a'): shutil.copytree(args[2], args[3])
                return ''

            def backup(work, dest):
                events.append(('backup',))
                if failure == 'backup': raise RuntimeError('backup failed')
                dest.mkdir()
                shutil.copytree(native / 'app', dest / 'native-app')

            def install(source):
                events.append(('install',))
                (native / 'app/version.py').write_text('new')

            with patch.object(deploy, 'Path', side_effect=lambda p: root / Path(p).name), \
                 patch.object(deploy.os, 'umask'), \
                 patch.object(sys, 'argv', ['deploy', release, 'deploy']), \
                 patch.multiple(deploy.r, NATIVE=native, APP=root / 'app',
                    prepare=lambda *_: (['old'], 'new-image'), sql=sql, compose=compose,
                    run=run, backup=backup, install_native=install,
                    inspect=lambda _: {'State': {'Running': False}}):
                with self.assertRaises(RuntimeError): deploy.main()
            return events, state, (native / 'app/version.py').read_text()

    def test_backup_failure_never_migrates_and_recovers_old_services(self):
        events, state, code = self.exercise('backup')
        self.assertEqual(state, {'schema': '0017', 'paused': False})
        self.assertEqual(code, 'old')
        self.assertNotIn(('install',), events)
        self.assertFalse(any(e[0] == 'compose' and 'migrate' in e[2] for e in events))
        self.assertTrue(any(e[0] == 'compose' and e[1] == ('old',) and e[2][-1] == 'web' for e in events))

    def test_failure_after_migration_restores_old_app_retains_schema(self):
        events, state, code = self.exercise('install')
        self.assertIn(('install',), events)
        self.assertEqual(code, 'old')
        self.assertEqual(state, {'schema': '0019', 'paused': False})

    def test_rollback_failure_keeps_intake_closed(self):
        events, state, code = self.exercise('rollback')
        self.assertEqual(code, 'old')
        self.assertTrue(state['paused'])
        self.assertEqual(events[-1][0], 'compose')
        self.assertEqual(events[-1][2], ('stop', '-t', '30', 'web', 'api', 'outbox', 'api-image-outbox'))


if __name__ == '__main__': unittest.main()
