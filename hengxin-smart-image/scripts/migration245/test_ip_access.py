"""Preparation isolation and pre-apply tamper rejection, without Docker/servers."""
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
from unittest.mock import patch

import ip_access as module
from build_edge import NGINX


class AccessPreparation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'ip-access-20261111'
        self.work.mkdir()
        self.files = {'app/core/config.py': b'config', 'app/core/browser_auth.py': b'cookie'}
        self.manifest = {'backend': {}, 'frontend': {'index.html': module.digest(b'html')}}
        for name, data in self.files.items():
            path = self.work / 'backend' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data + b'-new')
            self.manifest['backend'][name] = module.digest(data + b'-new')
        (self.work / 'frontend').mkdir()
        (self.work / 'frontend/index.html').write_bytes(b'html')
        (self.work / 'manifest.json').write_text(json.dumps(self.manifest))
        services = {name: {'container_name': name, 'environment': {'APP_ENV': 'production'},
                          'volumes': [], 'image': 'sha256:test'} for name in module.SERVICES}
        services['domestic-web']['volumes'] = [{'target': '/usr/share/nginx/html', 'source': 'original'}]
        self.original = json.dumps({'services': services}).encode()
        (self.root / 'compose.json').write_bytes(self.original)
        (self.root / 'edge-nginx.conf').write_bytes(NGINX.encode())
        for name, value in [('ROOT', self.root), ('WORK', self.work),
                            ('BASE', {n: module.digest(b) for n, b in self.files.items()})]:
            patcher = patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_run(self, args):
        return self.files[args[-1].removeprefix('/app/')] if 'cat' in args else b''

    def prepare(self):
        with patch.object(module, 'check'), patch.object(module, 'run', side_effect=self.fake_run):
            module.prepare()

    def test_prepare_does_not_modify_live_configuration(self):
        self.prepare()
        self.assertEqual((self.root / 'compose.json').read_bytes(), self.original)
        self.assertEqual((self.root / 'edge-nginx.conf').read_bytes(), NGINX.encode())
        candidate = json.loads((self.work / 'compose.candidate.json').read_text())['services']
        self.assertEqual(candidate['domestic-api']['environment']['APP_ENV'], 'production')
        self.assertEqual(candidate['overseas-api']['environment']['OVERSEAS_ALLOW_INTRANET_HTTP'], 'true')
        self.assertEqual(candidate['identity-api']['environment']['IDENTITY_PUBLIC_ORIGIN'], module.ORIGIN)

    def test_changed_frontend_refused_before_apply(self):
        self.prepare()
        (self.work / 'frontend/index.html').write_bytes(b'tampered')
        with patch.object(module, 'check'), self.assertRaisesRegex(RuntimeError, 'payload changed'):
            module.apply()
        self.assertEqual((self.root / 'compose.json').read_bytes(), self.original)

    def test_unexpected_live_source_refuses_prepare(self):
        self.files['app/core/config.py'] = b'unexpected deployment source'
        with patch.object(module, 'check'), patch.object(module, 'run', side_effect=self.fake_run):
            with self.assertRaisesRegex(RuntimeError, 'API source drift'):
                module.prepare()
        self.assertFalse((self.work / 'compose.candidate.json').exists())
        self.assertEqual((self.root / 'compose.json').read_bytes(), self.original)

    def test_nginx_reload_waits_for_entrypoint_pid(self):
        missing_pid = subprocess.CalledProcessError(1, ['nginx', '-s', 'reload'])
        with patch.object(module, 'run', side_effect=[b'', missing_pid, b'', b'']) as run:
            with patch.object(module.time, 'sleep') as sleep:
                module.reload_nginx('web')
        self.assertEqual(run.call_count, 4)
        sleep.assert_called_once_with(1)

    def test_restore_reloads_edge_even_when_web_restore_fails(self):
        self.prepare()
        with patch.object(module, 'compose', side_effect=RuntimeError('compose unavailable')):
            with patch.object(module, 'reload_nginx') as reload:
                with self.assertRaisesRegex(RuntimeError, 'compose unavailable'):
                    module.restore()
        reload.assert_called_once_with('hengxin-lan-https')
        self.assertEqual((self.root / 'edge-nginx.conf').read_bytes(), NGINX.encode())


if __name__ == '__main__':
    unittest.main()
