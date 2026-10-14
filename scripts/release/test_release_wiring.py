"""Release entry and archive integration checks without operating Docker or services."""
import ast
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
HELPERS = {'release-retention.py', 'release-retention-state.py',
           'release-retention-docker.py', 'release-build.py'}


@pytest.mark.parametrize('path', sorted(ROOT.glob('package*.py')), ids=lambda p: p.name)
def test_all_packages_include_helpers_without_selecting_tests(path):
    if path.name == 'package-image-inputs.py':
        # Historical top-level packager has side effects; evaluate only its allowlist.
        tree = ast.parse(path.read_text())
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'RELEASE_HELPERS' for t in node.targets))
        namespace = {'Path': Path, '__file__': str(path)}
        exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(path), 'exec'), namespace)
        assert HELPERS <= namespace['RELEASE_HELPERS']
        assert "names.extend('scripts/release/' + name for name in sorted(RELEASE_HELPERS))" in path.read_text()
        return
    spec = importlib.util.spec_from_file_location('package_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in HELPERS | {p.name for p in ROOT.glob('release-retention*.py')}:
        assert module.selected('scripts/release/' + name) == 'scripts/release/' + name
    for name in ('test_release_retention.py', 'release-retention.py.bak', '../release-retention.py',
                 'private/release-retention.py'):
        assert module.selected('scripts/release/' + name) is None


ENTRIES = [*ROOT.glob('*-deploy.py'), ROOT / 'member-release-resume.py', ROOT / 'overseas-codex-prepare.py']


@pytest.mark.parametrize('path', sorted(ENTRIES), ids=lambda p: p.name)
def test_cli_managed_wraps_main_outside_failure_handlers(path):
    tree = ast.parse(path.read_text())
    entry = next(node for node in tree.body if isinstance(node, ast.If)
                 and "__name__" in ast.unparse(node.test))
    calls = [node for node in ast.walk(entry) if isinstance(node, ast.Call)]
    managed = [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == 'managed']
    assert len(managed) == 1 and ast.unparse(managed[0].args[0]) == 'main'
    assert not any(isinstance(node.func, ast.Name) and node.func.id in {'main', 'deploy', 'resume'} for node in calls)
    for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)):
        assert '.managed(' not in ast.unparse(function)
