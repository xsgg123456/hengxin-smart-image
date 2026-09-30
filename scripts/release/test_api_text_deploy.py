"""Execute the deployment controller against simulated production failures."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deploy', Path(__file__).with_name('api-text-deploy.py'))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class RecoveryTests(unittest.TestCase):
    def test_installed_scope_only_excludes_repository_tools(self):
        args = deploy.installed_test_args()
        self.assertEqual(args[:3], ['-m', 'pytest', '-q'])
        self.assertEqual(sum(a.startswith('--ignore=') for a in args), 6)
        self.assertNotIn('--ignore=tests/test_contracts.py', args)
        self.assertIn('--deselect=tests/test_contracts.py::test_top_level_fields_match_frontend_interfaces', args)

    def exercise(self, failure, mode='deploy'):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release = 'api-text-20260930-abcdef0'
            work = root / 'hengxin-releases' / release
            source = work / 'src'
            source.mkdir(parents=True)
            (work / 'INSTALL_TEST_IMAGE_ID').write_text('image-id')
            (source / 'release.json').write_text(json.dumps(dict(
                release=release, migration='0022', frontendVersion='0.2.14')))
            helper = source / 'scripts/release/image-inputs-worker.py'
            helper.parent.mkdir(parents=True)
            helper.write_text('# test helper')
            native = root / 'app/backend'
            (native / 'app').mkdir(parents=True)
            (native / 'app/version.py').write_text('old')
            frontend = root / 'app/frontend'
            (frontend / 'dist').mkdir(parents=True)
            (frontend / 'dist/index.html').write_text('old-html')
            (frontend / 'package.json').write_text('old-package')
            markers = ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json', 'API_TEXT_RELEASE.json')
            for name in markers[:-1]: (root / 'app' / name).write_text('old-marker')
            (root / 'app/API_SIZE_RELEASE.json').write_text('historical-size')
            backup_root = root / 'hengxin-backups'
            backup_root.mkdir()
            events, state = [], {'schema': '0021', 'paused': False}

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
                if 'migrate' in args: state['schema'] = '0022'
                if failure == 'rollback' and paths == ['old'] and args[0] == 'up':
                    raise RuntimeError('rollback failed')
                return ''

            def run(*args, **kwargs):
                events.append(('run', args))
                if args[:3] == ('docker', 'image', 'inspect'): return 'image-id'
                if args[:3] == ('uv', 'pip', 'check') and failure not in ('drain', 'open', 'success', 'front'): raise RuntimeError('dependency verification failed')
                if failure == 'drain' and 'run-native-stop' in args: raise RuntimeError('uncertain stop')
                if failure == 'open' and args[:3] == ('docker', 'exec', deploy.r.PREFIX + 'web-1'): raise RuntimeError('reload failed')
                if args[:2] == ('systemctl', 'show'): return 'inactive'
                if args[:2] == ('cp', '-a'): shutil.copytree(args[2], args[3])
                return ''

            def backup(work, dest):
                events.append(('backup',))
                if failure == 'backup': raise RuntimeError('backup failed')
                dest.mkdir()
                (dest / 'COMPLETE').write_text('ok')
                shutil.copytree(native / 'app', dest / 'native-app')
                shutil.copy2(frontend / 'dist/index.html', dest / 'index.html')
                shutil.copy2(frontend / 'package.json', dest / 'frontend-package.json')
                for name in markers:
                    if (root / 'app' / name).exists(): shutil.copy2(root / 'app' / name, dest / name)

            def install(source):
                events.append(('install',))
                (native / 'app/version.py').write_text('new')

            def publish(*args):
                if failure != 'front': return
                (frontend / 'dist/index.html').write_text('new-html')
                (frontend / 'dist/index.html.gz').write_text('new-gzip')
                (frontend / 'package.json').write_text('new-package')
                for name in markers: (root / 'app' / name).write_text('new-marker')
                raise RuntimeError('publication interrupted')

            with patch.object(deploy, 'Path', side_effect=lambda p: root / Path(p).name), \
                 patch.object(deploy.os, 'umask'), \
                 patch.object(sys, 'argv', ['deploy', release, mode]), \
                 patch.object(deploy.subprocess, 'run'), \
                 patch.multiple(deploy.r, NATIVE=native, APP=root / 'app',
                    prepare=lambda *_: (['old'], 'new-image'), sql=sql, compose=compose,
                    run=run, backup=backup, install_native=install,
                    inspect=lambda _: {'State': {'Running': False}},
                    publish_frontend=publish):
                if failure == 'success': deploy.main()
                else:
                    with self.assertRaises(RuntimeError): deploy.main()
            if failure == 'front':
                self.assertEqual((frontend / 'dist/index.html').read_text(), 'old-html')
                self.assertFalse((frontend / 'dist/index.html.gz').exists())
                self.assertEqual((frontend / 'package.json').read_text(), 'old-package')
                self.assertFalse((root / 'app/API_TEXT_RELEASE.json').exists())
                self.assertEqual((root / 'app/API_SIZE_RELEASE.json').read_text(), 'historical-size')
                for name in markers[:-1]: self.assertEqual((root / 'app' / name).read_text(), 'old-marker')
            return events, state, (native / 'app/version.py').read_text()

    def test_partial_frontend_publication_restores_markers_and_package(self):
        events, state, code = self.exercise('front')
        self.assertEqual(code, 'old')
        self.assertEqual(state, {'schema': '0022', 'paused': False})

    def test_backup_failure_never_migrates_and_recovers_old_services(self):
        events, state, code = self.exercise('backup')
        self.assertEqual(state, {'schema': '0021', 'paused': False})
        self.assertEqual(code, 'old')
        self.assertNotIn(('install',), events)
        self.assertFalse(any(e[0] == 'compose' and 'migrate' in e[2] for e in events))
        self.assertTrue(any(e[0] == 'compose' and e[1] == ('old',) and e[2][-1] == 'web' for e in events))

    def test_failure_after_migration_restores_old_app_retains_schema(self):
        events, state, code = self.exercise('install')
        self.assertIn(('install',), events)
        self.assertEqual(code, 'old')
        self.assertEqual(state, {'schema': '0022', 'paused': False})

    def test_rollback_failure_keeps_intake_closed(self):
        events, state, code = self.exercise('rollback')
        self.assertEqual(code, 'old')
        self.assertTrue(state['paused'])
        self.assertEqual(events[-1], ('sql', 'UPDATE api_image_channel SET paused=true WHERE id=1'))


    def test_unknown_drain_never_restarts_workers(self):
        events, state, code = self.exercise('drain')
        self.assertEqual(code, 'old')
        self.assertTrue(state['paused'])
        self.assertFalse(any(e[0] == 'run' and e[1][:2] == ('systemctl', 'start') for e in events))

    def test_post_open_failure_retains_new_code(self):
        events, state, code = self.exercise('open')
        self.assertEqual(code, 'new')
        self.assertEqual(state, {'schema': '0022', 'paused': True})
        self.assertFalse(any(e[0] == 'compose' and e[1] == ('old',) and e[2][0] == 'up' for e in events))

    def test_success_stops_variants_before_backup(self):
        events, state, code = self.exercise('success')
        stop = next(i for i,e in enumerate(events) if e[0] == 'compose' and e[2] == ('stop', '-t', '30', 'image-variants'))
        self.assertLess(stop, events.index(('backup',)))
        self.assertEqual(state, {'schema': '0022', 'paused': False})
        self.assertEqual(code, 'new')

    def test_build_never_stops_or_changes_production(self):
        events, state, code = self.exercise('success', 'build')
        self.assertFalse(any(e[0] in ('compose', 'sql', 'install', 'backup') for e in events))
        self.assertEqual(code, 'old')

if __name__ == '__main__': unittest.main()
