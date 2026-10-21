import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('retention_package', Path(__file__).with_name('package-retention-management.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def valid():
    return {**{name: b'' for name in p.REQUIRED}, 'frontend/package.json': b'{"version":"0.2.46"}',
        'frontend/dist/index.html': b'<script src="/assets/main.js"></script>',
        'frontend/dist/assets/main.js': b'console.log(1)',
        'backend/migrations/versions/0032_retention_observability.py': b''}


@pytest.mark.parametrize('name', sorted(p.REQUIRED))
def test_required_dependencies_selected_and_enforced(name):
    if name.startswith('scripts/'):
        assert p.selected(name) == name
    files = valid()
    del files[name]
    with pytest.raises(ValueError, match='Missing'):
        p.validate(files)


def test_versions_and_committed_packaging_chain():
    p.validate(valid())
    assert p.package.VERSION == '0.2.46'
    assert p.package.DOMESTIC_MIGRATION == '0032'
    assert p.package.OVERSEAS_MIGRATION == 'overseas_0019'
    assert p.package.RELEASE_PREFIX == 'domestic-retention-20261021-'
    assert {'package-retention-management.py', 'package-api-simple.py', 'package-api-retry.py',
            'package-retirement.py', 'package-overseas.py'} <= set(p.package.PACKAGING_HELPERS)
    files = valid()
    files['frontend/package.json'] = b'{"version":"0.2.45"}'
    with pytest.raises(ValueError, match='version'):
        p.validate(files)


def test_migration_required_unique():
    files = valid()
    del files['backend/migrations/versions/0032_retention_observability.py']
    with pytest.raises(ValueError, match='0032'):
        p.validate(files)
    files = valid()
    files.update({'backend/migrations/versions/0032_two.py': b''})
    with pytest.raises(ValueError, match='0032'):
        p.validate(files)


@pytest.mark.parametrize('name', [
    'scripts/release/test_retention_management.py', 'scripts/retention-preview/retention.vue',
    'scripts/release/retention-management-deploy.py.bak', 'scripts/release/../retention-management-deploy.py',
    p.APP + 'backend/.env', p.APP + 'backend/private.db', p.APP + 'backend/auth.json',
])
def test_private_qa_files_excluded(name):
    assert p.selected(name) is None
