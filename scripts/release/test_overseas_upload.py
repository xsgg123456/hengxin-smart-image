"""Reuse drained-cutover fault matrix and exercise both proxy changes offline."""
import importlib.util
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


d = load('overseas-upload-deploy')
p = d.proxy
t = load('overseas-hotfix-tests')
t.d = d


class UploadReleaseTests(t.HotfixTests):
    def test_prepared_overlay_allows_only_api_image_build(self):
        source, image = self.root / 'src', 'sha256:test'
        baseline = {'services': {'api': {'image': 'old', 'mem_limit': '402653184',
                    'volumes': [{'target': '/skills', 'read_only': True}]}, 'migrate': {'image': 'old'}}}
        overlay = d.resources.overlay(source, image)
        t.save(self.root / 'overseas-overlay.json', overlay)
        t.save(self.root / 'overseas-compose.private.json', baseline)
        after = copy.deepcopy(baseline)
        after['services']['api'].update(overlay['services']['api'])
        compose = self.mock(d.m, 'compose', side_effect=[json.dumps(baseline), json.dumps(after)])
        d.prepared_settings(self.root, {'overseas': {}}, image, source)
        after['services']['api']['volumes'][0]['read_only'] = False
        compose.side_effect = [json.dumps(baseline), json.dumps(after)]
        with self.assertRaisesRegex(AssertionError, 'settings'):
            d.prepared_settings(self.root, {'overseas': {}}, image, source)
        overlay['services']['migrate'] = {'image': image}
        t.save(self.root / 'overseas-overlay.json', overlay)
        with self.assertRaisesRegex(AssertionError, 'overlay drift'):
            d.prepared_settings(self.root, {'overseas': {}}, image, source)

    def setup_deploy(self, failure=None):
        work, data, events = super().setup_deploy(failure)
        (work / 'UPLOAD_CAPACITY_IMAGE_ID').write_text('sha256:tested')
        for name in ('unchanged', 'install_inner', 'verify', 'restore_inner'):
            self.mock(p, name)
        (work / 'upload-edge-after.conf').write_text(d.m.EDGE.read_text())
        return work, data, events

    def test_optimized_python_aborts_before_production_actions(self):
        script = Path(__file__).with_name('overseas-upload-deploy.py')
        for flags, optimize in ((['-O'], '0'), ([], '1')):
            result = subprocess.run([sys.executable, *flags, str(script),
                'overseas-20261014-abcdef0', 'build'], capture_output=True, text=True,
                env={**os.environ, 'PYTHONOPTIMIZE': optimize}, timeout=30)
            assert result.returncode != 0
            assert 'RuntimeError: Python -O disables release safety assertions' in result.stderr

    def test_inner_proxy_installed_only_after_api_is_healthy(self):
        work, _, events = self.setup_deploy()
        p.install_inner.side_effect = lambda *args: events.append(('install-inner',))
        self.deploy(work)
        names = [event[0] for event in events]
        assert names.index('backup') < names.index('installed') < names.index('install-inner') < names.index('proxy')
        reload_index = next(i for i, event in enumerate(events) if event[0] == 'run' and event[-2:] == ('-s', 'reload'))
        assert names.index('install-inner') < reload_index < names.index('proxy')

    def test_proxy_failure_closes_intake_and_restores_inner(self):
        work, _, events = self.setup_deploy()
        p.verify.side_effect = RuntimeError('proxy-boundary')
        with self.assertRaisesRegex(RuntimeError, 'proxy-boundary'):
            self.deploy(work)
        p.restore_inner.assert_called_once_with(work, d.m)
        assert (work / 'FAILURE.json').exists()
        assert [event[0] for event in events].count('close') == 2


def test_proxy_patch_is_scoped_and_rejects_ambiguity():
    domestic = 'server { client_max_body_size 10m; location /api/v1/ { proxy_pass http://domestic; } '
    overseas = 'location ^~ /api/overseas/v1/ { proxy_pass http://overseas-api:8000; proxy_read_timeout 300s; }'
    original = domestic + overseas + '}'
    changed = p.patch(original, p.DIRECTIVES)
    assert changed.startswith(domestic)
    assert 'proxy_pass http://overseas-api:8000;' in changed
    assert changed.count('proxy_read_timeout') == 1
    assert 'client_max_body_size 500065536;' in changed
    for bad in (domestic + '}', original + overseas):
        with pytest.raises(AssertionError):
            p.patch(bad, p.DIRECTIVES)


def test_proxy_backup_install_restore(tmp_path):
    work, backup, source = [tmp_path / name for name in ('work', 'backup', 'source')]
    for folder in (work, backup, source / 'infra', tmp_path / 'infra'):
        folder.mkdir(parents=True, exist_ok=True)
    original = 'client_max_body_size 10m; location ^~ /api/overseas/v1/ { proxy_pass http://upstream; }'
    edge = tmp_path / 'edge.conf'; edge.write_text(original)
    inside = tmp_path / 'infra/nginx.vps.conf'; inside.write_text(original)
    (source / 'infra/nginx.overseas-upload.inc').write_text(''.join(f'{k} {v};\n' for k,v in p.DIRECTIVES.items()))
    m = SimpleNamespace(APP=tmp_path, EDGE=edge, private=lambda path,value:path.write_text(value), run=Mock(),r=SimpleNamespace(PREFIX='web-'))
    p.prepare(work, source, m); p.unchanged(work, m)
    with pytest.raises(AssertionError): p.install_inner(work, backup, m)
    (backup / 'COMPLETE').write_text('verified')
    p.install_inner(work, backup, m)
    assert (backup / 'upload-inner.conf').read_text() == original
    assert inside.read_text() != original
    p.restore_inner(work,m); assert inside.read_text() == original
    inside.write_text(original + '# concurrent update')
    with pytest.raises(AssertionError): p.unchanged(work,m)
# The inherited failure matrix creates fresh cases by the module's class name.
t.HotfixTests = UploadReleaseTests


def test_only_exact_api_memory_override_is_allowed():
    before = {'services': {'api': {'image': 'old', 'mem_limit': '402653184',
              'environment': {'SAFE': 'yes'}}, 'other': {'image': 'unchanged'}}}
    after = copy.deepcopy(before)
    after['services']['api'].update(d.resources.overlay('/source', 'tested')['services']['api'])
    after['services']['api']['mem_limit'] = str(d.resources.API_MEMORY)
    d.resources.same_settings(before, after, d.m)
    for field, value in (('mem_limit', '402653184'), ('environment', {'SAFE': 'no'})):
        changed = copy.deepcopy(after)
        changed['services']['api'][field] = value
        with pytest.raises(AssertionError): d.resources.same_settings(before, changed, d.m)
    changed = copy.deepcopy(after)
    changed['services']['other']['image'] = 'unexpected'
    with pytest.raises(AssertionError): d.resources.same_settings(before, changed, d.m)
