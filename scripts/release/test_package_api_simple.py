import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('simple_package', Path(__file__).with_name('package-api-simple.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def valid():
    return {**{name: b'' for name in p.REQUIRED}, 'frontend/package.json': b'{"version":"0.2.45"}',
        'frontend/dist/index.html': b'<script src="/assets/main.js"></script>',
        'frontend/dist/assets/main.js': b'console.log(1)'}


@pytest.mark.parametrize('name', sorted(p.REQUIRED))
def test_required_release_dependencies_are_selected_and_enforced(name):
    if name.startswith('scripts/'):
        assert p.selected(name) == name
    files = valid()
    del files[name]
    with pytest.raises(ValueError, match='Missing'):
        p.validate(files)


def test_current_package_version_and_helpers():
    p.validate(valid())
    assert p.package.VERSION == '0.2.45'
    assert p.package.DOMESTIC_MIGRATION == '0031'
    assert p.package.OVERSEAS_MIGRATION == 'overseas_0019'
    assert p.package.RELEASE_PREFIX == 'domestic-api-simple-20261020-'
    assert {'package-api-simple.py', 'package-api-retry.py', 'package-retirement.py',
            'package-overseas.py'} <= set(p.package.PACKAGING_HELPERS)
    files = valid()
    files['frontend/package.json'] = b'{"version":"0.2.44"}'
    with pytest.raises(ValueError, match='version'):
        p.validate(files)


@pytest.mark.parametrize('name', [
    'scripts/api-retry/simple-live-app.py', 'scripts/api-retry/simple-live-browser.mjs',
    'scripts/release/test_api_simple_deploy.py', 'scripts/release/test_api_simple_handoff.py',
    'scripts/release/api-simple-deploy.py.bak', 'scripts/release/../api-simple-deploy.py',
    p.APP + 'backend/.env', p.APP + 'backend/private.db', p.APP + 'backend/auth.json',
])
def test_local_qa_and_private_files_are_not_packaged(name):
    assert p.selected(name) is None
