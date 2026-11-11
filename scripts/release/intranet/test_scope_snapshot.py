"""Mixed actual source paths, group projection and runtime census evidence."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import engine
import image_gc
import scopes
import scope_snapshot as ss
import snapshot

VERIFY_FRONTEND = ss.verify_frontend

class ScopeSnapshotTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        p = patch.object(snapshot, 'RELEASES', self.root)
        p.start()
        self.addCleanup(p.stop)
        self.live, self.ctx, self.native_roots, self.manifests = {}, {}, {}, {}
        for scope in scopes.GROUPS:
            backend, frontend = self.root / (scope + '-backend'), self.root / (scope + '-frontend')
            for root in (backend, frontend):
                root.mkdir()
                manifest = {'commit': 'a' * 40, 'files': {'backend/app/main.py': scope + '-code',
                                                        'frontend/index.html': scope + '-html'}}
                (root / 'release-manifest.json').write_text(json.dumps(manifest))
                self.manifests[str(root)] = manifest
            for name in scopes.APPS[scope]:
                self.live[name] = self.info(name, '/app/app', str(backend / 'backend/app'))
            self.live[scopes.UI[scope]] = self.info(scopes.UI[scope], '/usr/share/nginx/html', str(frontend / 'frontend'))
            self.live[scopes.UI[scope]]['Mounts'].append({'Destination': '/usr/share/nginx/previous', 'Source': str(frontend/'frontend'), 'RW': False})
            for name in scopes.NATIVE[scope]:
                self.ctx[name] = dict(cwd=str(backend / 'backend'), python='/python', user=1000, group=1000, extra_groups=[])
                self.native_roots[str(len(self.native_roots) + 100)] = str(backend / 'backend')
        self.pids = dict(zip(self.ctx, self.native_roots))
        self.live['domestic-web'] = self.info('domestic-web', '/usr/share/nginx/html', '/legacy/frontend')
        self.u = SimpleNamespace(APPS=engine.u.APPS, DATA=engine.u.DATA, NATIVE=engine.u.NATIVE,
                                 PYTHON_SERVICES=engine.u.PYTHON_SERVICES, WORKERS=engine.u.WORKERS,
                                 RELEASE=self.root / 'untouched', validate_release=Mock(return_value='valid'),
                                 containers=Mock(side_effect=lambda: self.live), contexts=Mock(return_value=self.ctx),
                                 prop=Mock(side_effect=lambda n, k: self.pids[n] if k == 'MainPID' else '12345'),
                                 native_run=Mock(return_value='{}'), health=Mock(), data_identity=Mock(return_value={'data': 'same'}),
                                 config_paths=Mock(return_value=[]), safe=Mock(), run=Mock(side_effect=self.command))
        self.images = {n: 'sha256:' + 'a' * 64 for n in image_gc.expected(image_gc.scoped(self.u))}
        for p in (patch.object(ss, 'verify_frontend'), patch.object(snapshot, 'schemas', return_value={'domestic': 'd', 'overseas': 'o'}),
                  patch.object(image_gc, 'capture', return_value=self.images),
                  patch.object(ss.os, 'readlink', side_effect=lambda path: self.native_roots[path.split('/')[2]])):
            p.start()
            self.addCleanup(p.stop)

    @staticmethod
    def info(name, target, source):
        return dict(Id=name + '-id', Image='sha256:' + 'a' * 64, Name='/hengxin-lan-' + name,
                    Config={'Labels': {'com.docker.compose.project': 'hengxin-lan-edge' if name == 'https' else 'hengxin-lan',
                                       'com.docker.compose.service': name}},
                    State={'Running': True, 'StartedAt': 'unchanged'},
                    Mounts=[{'Destination': target, 'Source': source, 'RW': False}])

    def command(self, argv, **kwargs):
        name = argv[2].removeprefix('hengxin-lan-')
        scope = next(s for s in scopes.GROUPS if name in scopes.APPS[s])
        return json.dumps({'app/main.py': scope + '-code'})

    def test_capture_accepts_three_backends_and_distinct_frontends(self):
        result = ss.capture(self.u, runtime=True)
        self.assertEqual(len(result['groups']), 3)
        self.assertEqual(len(result['images']), 20)
        self.assertEqual(len(result['native']), 7)
        self.assertEqual(len(result['binaries']), 2)
        self.assertEqual(len(result['asset_fallbacks']), 3)
        self.assertEqual(self.u.RELEASE, self.root / 'untouched')
        for s in scopes.GROUPS:
            self.assertEqual(result['groups'][s]['backend'], str(self.root / (s + '-backend')))
            self.assertEqual(result['groups'][s]['frontend'], str(self.root / (s + '-frontend')))
        runtime = [c for c in self.u.native_run.call_args_list if c.kwargs.get('module') == 'app.execution.runtime_check']
        self.assertEqual(len(runtime), 2)

    def test_actual_code_mismatch_refuses(self):
        self.u.run.side_effect = lambda *a, **kw: '{}'
        with self.assertRaisesRegex(RuntimeError, 'Live source mismatch'):
            ss.capture(self.u)

    def test_writable_previous_frontend_refuses(self):
        self.live['domestic-ui']['Mounts'][1]['RW'] = True
        with self.assertRaisesRegex(RuntimeError, 'read-only previous'):
            ss.capture(self.u)

    def test_native_actual_cwd_mismatch_refuses(self):
        self.native_roots[self.pids['hengxin-overseas-worker']] = '/wrong/backend'
        with self.assertRaisesRegex(RuntimeError, 'Native process source mismatch'):
            ss.capture(self.u)

    def test_mixed_sources_inside_one_group_refuse(self):
        self.live['domestic-outbox']['Mounts'][0]['Source'] = str(self.root / 'other/backend/app')
        with self.assertRaisesRegex(RuntimeError, 'Group containers run mixed'):
            ss.capture(self.u)

    def test_ledger_group_excludes_other_side_and_global_config(self):
        before = ss.capture(self.u)
        after = copy.deepcopy(before)
        after['groups']['overseas']['backend'] = '/new'
        after['images']['overseas-api'] = 'new-image'
        after['configs']['compose'] = 'new-hash'
        self.assertEqual(ss.group(before, 'domestic'), ss.group(after, 'domestic'))
        self.assertNotEqual(ss.group(before, 'overseas'), ss.group(after, 'overseas'))

    def test_nginx_config_bind_inventory_includes_gateway_and_three_ui(self):
        files = []
        for name in ('domestic-web', *scopes.UI.values()):
            path = self.root / (name + '.conf')
            path.write_text(name)
            files.append(path)
            self.live[name]['Mounts'].append({'Destination': '/etc/nginx/conf.d/default.conf', 'Source': str(path), 'RW': False})
        self.assertEqual(ss.config_paths(self.u, self.live), sorted(files))
        self.live['domestic-ui']['Mounts'][-1]['RW'] = True
        with self.assertRaisesRegex(RuntimeError, 'read-only nginx'):
            ss.config_paths(self.u, self.live)

    def test_frontend_checks_each_real_prefix_and_rejects_other_index(self):
        response = Mock(status=200)
        response.read.return_value = b'correct-index'
        opener = Mock()
        opener.return_value.__enter__ = Mock(return_value=response)
        opener.return_value.__exit__ = Mock(return_value=False)
        manifest = {'files': {'frontend/index.html': snapshot.sha(b'correct-index')}}
        with patch.object(ss.urllib.request, 'urlopen', opener):
            for scope in scopes.GROUPS:
                VERIFY_FRONTEND(scope, manifest)
                self.assertEqual(opener.call_args.args[0], f'http://192.168.1.245:8080/{scope}/')
            response.read.return_value = b'wrong-scope-index'
            with self.assertRaisesRegex(RuntimeError, 'Served frontend differs'):
                VERIFY_FRONTEND('domestic', manifest)

    def test_census_and_unchanged_other_detect_pid_and_start_drift(self):
        inventory = list(self.live.values()) + [self.info(n, '/data', '/data') for n in (*self.u.DATA, 'https')]
        with patch.object(image_gc, 'containers', return_value=inventory):
            before = ss.census(self.u)
        self.assertEqual(len(before['containers']), 20)
        after = copy.deepcopy(before)
        after['native']['hengxin-vps-codex-worker']['pid'] = 'new'
        after['containers']['domestic-api']['started'] = 'new'
        ss.unchanged_other(before, after, 'domestic')
        with self.assertRaisesRegex(RuntimeError, 'Unaffected runtime changed'):
            ss.unchanged_other(before, after, 'overseas')
        with self.assertRaisesRegex(RuntimeError, 'Unaffected runtime changed'):
            ss.unchanged_other(before, after, 'domestic', 'frontend')


if __name__ == '__main__':
    unittest.main()
