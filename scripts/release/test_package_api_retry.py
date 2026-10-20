import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('retry_package', Path(__file__).with_name('package-api-retry.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def valid():
    return {**{name: b'' for name in p.REQUIRED}, 'frontend/package.json': b'{"version":"0.2.44"}',
        'frontend/dist/index.html': b'<script src="/assets/main.js"></script>',
        'frontend/dist/assets/main.js': b'console.log(1)'}


def test_package_requires_new_migration_and_release_entry():
    p.validate(valid())
    for name in ('backend/migrations/versions/0031_api_retry_policy.py', 'scripts/release/api-retry-deploy.py'):
        files = valid()
        del files[name]
        with pytest.raises(ValueError, match='Missing'): p.validate(files)
    assert p.p.p.DOMESTIC_MIGRATION == '0031'
    assert p.p.p.OVERSEAS_MIGRATION == 'overseas_0019'
    assert p.p.p.RELEASE_PREFIX.startswith('domestic-')


def test_package_excludes_runtime_secrets_images_and_development_sources():
    for name in ('backend/.env', 'backend/image.jpg', 'backend/auth.json', 'frontend/src/main.ts'):
        assert p.selected(p.APP + name) is None
    assert p.selected('scripts/release/api-retry-deploy.py') == 'scripts/release/api-retry-deploy.py'
    for name in p.REQUIRED:
        if name.startswith('scripts/'):
            assert p.selected(name) == name


def test_version_and_static_whitelist_remain_enforced():
    files = valid()
    files['frontend/package.json'] = json.dumps({'version': '0.2.43'}).encode()
    with pytest.raises(ValueError, match='version'): p.validate(files)
    for name in ('.env', 'auth.json', 'private.db', 'assets/main.js.map'):
        with pytest.raises(ValueError): p.p.p.audit_asset('frontend/dist/' + name, b'secret', Path('unused'))
