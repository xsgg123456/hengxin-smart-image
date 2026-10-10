import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('usage_package', Path(__file__).with_name('package-usage-total.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def test_only_explicit_sources_and_release_helpers_are_selected():
    for path in ('hengxin-smart-image/backend/.env', 'hengxin-smart-image/backend/local.db',
                 'hengxin-smart-image/frontend/src/private.ts', 'scripts/release/management-deploy.py',
                 'output/auth.json', '.codex/sessions/private.jsonl'):
        assert p.selected(path) is None
    for name in p.SCRIPTS:
        assert p.selected('scripts/release/' + name) == 'scripts/release/' + name
    assert p.selected('hengxin-smart-image/backend/app/modules/management/api_usage.py')


def test_release_requires_correct_version_and_complete_runtime():
    files = {name: b'' for name in p.m.EXACT}
    files.update({'scripts/release/' + name: b'' for name in p.SCRIPTS})
    files['frontend/dist/index.html'] = b'<html></html>'
    files['frontend/package.json'] = json.dumps({'version': '0.2.21'}).encode()
    for name in ('0024_cli_retention.py', '0025_api_usage_facts.py', '0026_api_worker_heartbeat.py'):
        files['backend/migrations/versions/' + name] = b''
    for name in ('app/contracts/api_usage.py', 'app/modules/management/api_usage.py',
                 'app/modules/management/api_usage_summary.py', 'tests/test_usage_generated_totals.py'):
        files['backend/' + name] = b''
    p.validate(files)
    with pytest.raises(AssertionError):
        p.validate({**files, 'frontend/package.json': b'{"version":"0.2.20"}'})
    del files['scripts/release/usage-total-verify.py']
    with pytest.raises(AssertionError):
        p.validate(files)


@pytest.mark.parametrize('name,body', [('assets/.env', b'hello'), ('assets/local.db', b'hello'),
    ('assets/main.js', b'const bad = "sk-' + b'a' * 25 + b'"'),
    ('assets/main.js', b'const bad = "C:/Users/local/source"')])
def test_privacy_rejects_unsafe_assets(name, body):
    with pytest.raises(ValueError):
        p.m.audit_asset(name, body)


def test_roundtrip_archive_rejects_path_escape():
    with pytest.raises(ValueError):
        p.m.archive_bytes({'../outside.py': b'x'})
    assert p.m.archive_bytes({'backend/app/main.py': b'app=1'}) == p.m.archive_bytes({'backend/app/main.py': b'app=1'})
