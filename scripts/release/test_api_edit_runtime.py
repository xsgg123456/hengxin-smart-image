"""The new release must preserve every live deployment overlay."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('text_runtime', Path(__file__).with_name('api-edit-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class RuntimeTests(unittest.TestCase):
    def test_overlay_preserves_all_existing_variant_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            native = work / 'native'
            source = work / 'src/backend'
            native.mkdir(); source.mkdir(parents=True)
            for name in ('pyproject.toml', 'uv.lock'):
                (native / name).write_text('same')
                (source / name).write_text('same')
            paths = ['/opt/existing-' + str(i) + '.yaml' for i in range(11)]
            previous = 'hengxin-smart-image-backend:api-text-20260930-fc3dbbd'
            services = {name: {'image': previous, 'environment': {'PRESERVE': '1'},
                'command': ['existing', name], 'cpus': 0.5, 'mem_limit': '777m',
                'networks': {'isolated': None}} for name in r.SERVICES}
            def inspect(name):
                return {'State': {'Running': True}, 'Config': {'Image': previous,
                    'Env': ['PRESERVE=1'], 'Cmd': ['existing', name], 'Labels': {
                        'com.docker.compose.project.config_files': ','.join(paths)}}}
            def compose(*args, **kwargs):
                return json.dumps({'services': services}) if kwargs.get('capture') else ''
            with patch.multiple(r, NATIVE=native, inspect=inspect, compose=compose,
                                Path=lambda _: SimpleNamespace(is_file=lambda: True)):
                found, image = r.prepare(work, {'release': 'api-edit-20260930-abcdef0', 'files': {}})
            self.assertEqual(found, paths)
            overrides = json.loads((work / 'api-override.yaml').read_text())['services']
            self.assertEqual(set(overrides), {*r.SERVICES, 'migrate'})
            for values in overrides.values():
                self.assertEqual(set(values), {'image', 'build'})
                self.assertEqual(values['image'], image)
            self.assertEqual(json.loads((work / 'old-paths.json').read_text()), paths)


class ResourceTests(unittest.TestCase):
    def test_native_resource_allowlist_contains_all_three_templates(self):
        self.assertEqual(r.NATIVE_RESOURCES, {
            'modules/api_image_edits/image_edit_prompt.txt',
            'modules/api_image_edits/text_edit_prompt.txt',
            'modules/api_image_edits/text_repair_prompt.txt',
        })

    def test_native_installs_prompt_bytes_without_unlisted_resources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            native, source = root / 'native', root / 'source'
            (native / 'app').mkdir(parents=True)
            app = source / 'backend/app'
            app.mkdir(parents=True)
            (app / 'main.py').write_bytes(b'# code')
            (app / 'unexpected.txt').write_bytes(b'not allowed')
            for name in r.NATIVE_RESOURCES:
                target = app / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(('prompt:' + name).encode())
            with patch.object(r, 'NATIVE', native), patch.object(r.os, 'chown', create=True):
                r.install_native(source)
            for name in {*r.NATIVE_RESOURCES, 'main.py'}:
                self.assertEqual((native / 'app' / name).read_bytes(), (app / name).read_bytes())
            self.assertFalse((native / 'app/unexpected.txt').exists())

    def test_missing_prompt_stops_native_install_before_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'native/app').mkdir(parents=True)
            (root / 'source/backend/app').mkdir(parents=True)
            with patch.object(r, 'NATIVE', root / 'native'):
                with self.assertRaises(AssertionError): r.install_native(root / 'source')

    def test_publication_updates_active_markers_preserves_historical_size_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app, source = root / 'app', root / 'source'
            (app / 'frontend/dist').mkdir(parents=True)
            (source / 'frontend/dist').mkdir(parents=True)
            (source / 'frontend/dist/index.html').write_text('new')
            (source / 'frontend/package.json').write_text('{"version":"0.2.15"}')
            (app / 'API_SIZE_RELEASE.json').write_bytes(b'previous release')
            manifest = {'release': 'api-edit-20260930-abcdef0', 'migration': '0022', 'frontendVersion': '0.2.15'}
            with patch.object(r, 'APP', app):
                r.publish_frontend(source, root, manifest, ['base', 'old-override'])
            self.assertEqual((app / 'API_SIZE_RELEASE.json').read_bytes(), b'previous release')
            for name in ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json', 'API_TEXT_RELEASE.json', 'API_EDIT_RELEASE.json'):
                marker = json.loads((app / name).read_text())
                self.assertEqual(marker['release'], manifest['release'])
                self.assertEqual(marker['composeBaseOverlays'], ['base', 'old-override'])


if __name__ == '__main__': unittest.main()
