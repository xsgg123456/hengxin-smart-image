"""No-migration reopening release protections and inherited fault matrix."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock
import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s = load('overseas-studio-reopen-deploy')
p = load('package-studio-reopen')
baseline = load('test_studio_ux_release')
baseline.d = baseline.t.d = baseline.t.t.d = s.d
baseline.t.p = s.d.proxy
baseline.a = s.a.a


class StudioReopenReleaseTests(baseline.StudioUXReleaseTests):
    pass


def test_pinned_baseline_and_shared_services_preserved():
    assert s.a.BASE_VERSION == s.d.BASE_VERSION == '0.2.42'
    assert s.d.TARGET_VERSION == p.p.VERSION == '0.2.43'
    assert s.d.TARGET_MIGRATION == p.p.OVERSEAS_MIGRATION == 'overseas_0019'
    assert s.a.BASE_RELEASE == 'overseas-20261019-daf9d5e'
    assert s.a.BASE_IMAGE == 'sha256:572ab29546b72b7c7fbc32156550991b7806568eeaaeff5d437752fc80572950'
    assert all(path.as_posix().endswith('/overseas-20261019-daf9d5e/backend') for path in s.a.OVERSEAS_PATHS.values())
    assert s.d.domestic_native is s.a.domestic_native
    assert s.d.before_switch is s.verify_unchanged_data
    assert s.u.DROP > 'zzzzz-archive-deletion-20261019.conf'


@pytest.mark.parametrize('fault', [None, 'backup', 'drain', 'schema', 'data'])
def test_cutover_requires_backup_drain_and_exact_rows_without_migration(tmp_path, monkeypatch, fault):
    work, backup = tmp_path / 'work', tmp_path / 'backup'
    work.mkdir(); backup.mkdir()
    if fault != 'backup': (backup / 'COMPLETE').touch()
    if fault != 'drain': (work / 'EXECUTORS_STOPPED').touch()
    (backup / 'fingerprints.json').write_text(json.dumps({'tasks': 'unchanged'}))
    monkeypatch.setattr(s, 'schemas', Mock(side_effect=AssertionError('schema') if fault == 'schema' else None))
    monkeypatch.setattr(s.a.a, 'fingerprint', lambda _: {'tasks': 'changed' if fault == 'data' else 'unchanged'})
    action = Mock(side_effect=AssertionError('No production commands permitted'))
    monkeypatch.setattr(s.m, 'compose', action)
    monkeypatch.setattr(s.m, 'private', lambda path, value: path.write_text(value))
    if fault:
        with pytest.raises(AssertionError): s.verify_unchanged_data(work, None, None, None, backup)
        assert not (work / 'SCHEMA_UNCHANGED').exists()
    else:
        s.verify_unchanged_data(work, None, None, None, backup)
        assert 'overseas_0019' in (work / 'SCHEMA_UNCHANGED').read_text()
    action.assert_not_called()


def test_schema_hooks_use_existing_revision(monkeypatch):
    check = Mock()
    monkeypatch.setattr(s.a, 'check_schema', check)
    s.d.schemas(); s.a.schemas(); s.d.installed_schemas()
    assert check.call_count == 3
    check.assert_called_with('overseas_0019', '1')


def test_packaging_excludes_preview_and_includes_deployment_chain():
    assert p.selected('hengxin-smart-image/frontend/preview-studio-reopen/App.vue') is None
    assert p.selected('hengxin-smart-image/backend/app/overseas/studio/service.py') == 'backend/app/overseas/studio/service.py'
    seen, pending = set(), ['overseas-studio-reopen-deploy.py', 'release-retention.py']
    while pending:
        name = pending.pop()
        if name in seen: continue
        seen.add(name)
        assert p.selected('scripts/release/' + name) == 'scripts/release/' + name
        for node in ast.walk(ast.parse(Path(__file__).with_name(name).read_text(encoding='utf-8'))):
            if isinstance(node, ast.Call) and node.args and isinstance(node.func, ast.Attribute):
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if node.func.attr == 'with_name' and arg.value.endswith('.py'): pending.append(arg.value)
                    elif node.func.attr == 'module': pending.append(arg.value + '.py')


def test_optimized_python_aborts_before_actions():
    result = subprocess.run([sys.executable, '-O', str(Path(__file__).with_name('overseas-studio-reopen-deploy.py')),
        'overseas-20261019-abcdef0', 'build'], capture_output=True, text=True,
        env={**os.environ, 'PYTHONOPTIMIZE': '1'}, timeout=30)
    assert result.returncode != 0
    assert 'Python -O disables release safety assertions' in result.stderr
