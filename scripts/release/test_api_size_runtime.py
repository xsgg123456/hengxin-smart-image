"""The new release must preserve every live deployment overlay."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('text_runtime', Path(__file__).with_name('api-size-runtime.py'))
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
            previous = 'hengxin-smart-image-backend:text-edit-20260928-0ebb3bc'
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
                found, image = r.prepare(work, {'release': 'api-size-20260929-abcdef0', 'files': {}})
            self.assertEqual(found, paths)
            overrides = json.loads((work / 'api-override.yaml').read_text())['services']
            self.assertEqual(set(overrides), {*r.SERVICES, 'migrate'})
            for values in overrides.values():
                self.assertEqual(set(values), {'image', 'build'})
                self.assertEqual(values['image'], image)
            self.assertEqual(json.loads((work / 'old-paths.json').read_text()), paths)


if __name__ == '__main__': unittest.main()
