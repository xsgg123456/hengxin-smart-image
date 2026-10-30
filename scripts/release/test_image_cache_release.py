"""Guard scope, package path verification and retained static rollback."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r, f, d = load('image-cache-runtime'), load('image-cache-frontend'), load('image-cache-deploy')


class ReleaseTests(unittest.TestCase):
    def test_scope_only_overseas_and_no_dependency_recreation(self):
        self.assertTrue(all(n.startswith('app/overseas/') for n in r.FILES))
        self.assertEqual(r.ENV, {'OVERSEAS_CODEX_TIMEOUT_SECONDS':'7200', 'OVERSEAS_QUEUE_VISIBILITY_SECONDS':'7800'})
        source = Path(d.__file__).read_text(encoding='utf-8')
        self.assertIn("'--no-deps', '--no-build', 'api'", source)
        self.assertIn("worker_probe('overseas', 'drain-stop'", source)
        self.assertIn("EnvironmentFile=", source)

    def test_worker_switch_refuses_changed_identity_before_drain(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(d, 'state', return_value=({'units':{}}, None)), patch.object(d.r, 'unit_state', return_value={'pid':9}), patch.object(d.r.a, 'worker_probe') as probe:
                with self.assertRaisesRegex(RuntimeError, 'baseline drift'):
                    d.workers(Path(folder))
                probe.assert_not_called()

    def test_manifest_cannot_escape_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'source'
            source.mkdir()
            (root/'outside').write_text('x')
            manifest = dict(version='0.2.55', api={'files':dict.fromkeys(r.FILES)}, files={'../outside':r.digest(root/'outside')})
            (source/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError, 'Unsafe package'):
                r.verify_package(source)

    def test_frontend_rollback_retains_both_asset_generations(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, app, backup = root/'source', root/'app', root/'backup'
            for path in (source/'frontend/dist/assets',app/'frontend/dist/assets'):
                path.mkdir(parents=True)
            (app/'frontend/dist/index.html').write_text('old')
            (app/'frontend/dist/assets/old.js').write_text('old code')
            (app/'frontend/package.json').write_text('{"version":"0.2.54"}')
            (source/'frontend/dist/index.html').write_text('new')
            (source/'frontend/dist/assets/new.js').write_text('new code')
            (source/'frontend/package.json').write_text('{"version":"0.2.55"}')
            files = {p.relative_to(source).as_posix():r.digest(p) for p in source.rglob('*') if p.is_file()}
            (source/'release.json').write_text(json.dumps({'files':files}))
            with patch.object(f.r, 'verify_package', return_value={'files':files}):
                self.assertEqual(f.deploy(source,app,backup), 'FRONTEND_0.2.55_INSTALLED')
            f.rollback(app,backup)
            self.assertEqual((app/'frontend/dist/index.html').read_text(),'old')
            self.assertTrue((app/'frontend/dist/assets/new.js').exists())
            self.assertTrue((app/'frontend/dist/assets/old.js').exists())


if __name__ == '__main__':
    unittest.main()
