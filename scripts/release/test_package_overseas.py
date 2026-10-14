import gzip
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('overseas_package', Path(__file__).with_name('package-overseas.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


@pytest.fixture
def package_files():
    files = {name: b'' for name in p.REQUIRED}
    files['frontend/package.json'] = json.dumps({'version': '0.2.31'}).encode()
    files['frontend/dist/index.html'] = b'<html><script src="/assets/main.js"></script></html>'
    files['frontend/dist/assets/main.js'] = b'console.log(1)'
    return files


def test_allowlist_covers_runtime_and_only_explicit_non_python_resources():
    for path in p.EXACT:
        assert p.selected(p.APP + path) == path
    for path in ('backend/app/overseas/main.py', 'backend/app/identity/main.py',
                 'backend/migrations/overseas/versions/0009_management.py',
                 'backend/tests/test_overseas_management.py'):
        assert p.selected(p.APP + path) == path
    assert p.selected('scripts/release/overseas-runtime.py')
    assert p.selected('scripts/release/member-release-deploy.py')
    for name in p.MAINTENANCE:
        assert p.selected('scripts/maintenance/' + name)
    for path in ('backend/.env', 'backend/app/.env.py', 'backend/app/private.db',
                 'backend/app/key.pem', 'frontend/src/main.ts', 'frontend/dist/index.html',
                 'infra/.env.overseas.example', 'backend/app/../secrets.py'):
        assert p.selected(p.APP + path) is None
    for path in ('scripts/release/management-deploy.py', 'scripts/release/overseas.env',
                 'scripts/release/overseas/x.py', 'output/auth.json', '.codex/sessions/a.jsonl',
                 'scripts/maintenance/private.json', 'scripts/maintenance/approved-list.json'):
        assert p.selected(path) is None


def test_every_required_file_is_enforced(package_files):
    p.validate(package_files)
    for name in p.REQUIRED:
        with pytest.raises(ValueError, match='Missing required'):
            p.validate({k: v for k, v in package_files.items() if k != name})


def test_version_and_complete_production_entry(package_files):
    for value in ('0.2.21', '0.2.23'):
        with pytest.raises(ValueError, match='version'):
            p.validate({**package_files, 'frontend/package.json': json.dumps({'version': value}).encode()})
    with pytest.raises(ValueError, match='Missing frontend entry'):
        p.validate({k: v for k, v in package_files.items() if k != 'frontend/dist/assets/main.js'})
    with pytest.raises(ValueError, match='Preview'):
        p.validate({**package_files, 'frontend/dist/overseas-preview.html': b'demo'})
    with pytest.raises(ValueError, match='JavaScript'):
        p.validate({**package_files, 'frontend/dist/index.html': b'<html></html>'})


def test_asset_collection_excludes_demo_images_and_scans_compressed_assets(tmp_path):
    (tmp_path / 'demo-images').mkdir()
    (tmp_path / 'demo-images/private.db').write_bytes(b'not deployable')
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets/main.js').write_bytes(b'console.log(1)')
    assert set(p.collect_assets(tmp_path)) == {'frontend/dist/assets/main.js'}
    (tmp_path / 'assets/main.js.gz').write_bytes(gzip.compress(('sk-' + 'x' * 30).encode()))
    with pytest.raises(ValueError, match='Privacy'):
        p.collect_assets(tmp_path)


@pytest.mark.parametrize('name,body', [('.env', b'x'), ('credentials.json', b'x'),
    ('private.db', b'x'), ('main.js.map', b'x'), ('secret.key', b'x'),
    ('main.js', b'const key="sk-' + b'x' * 30 + b'"'),
    ('main.js', b'const path="C:/Users/developer/project"')])
def test_sensitive_assets_never_enter_package(tmp_path, name, body):
    (tmp_path / name).write_bytes(body)
    with pytest.raises(ValueError):
        p.collect_assets(tmp_path)


def test_source_scan_rejects_embedded_credentials():
    with pytest.raises(ValueError, match='Privacy'):
        p.m.common.privacy_check('backend/app/overseas/config.py', ('API_KEY="sk-' + 'x' * 30 + '"').encode())


@pytest.mark.parametrize('resource,asset', [
    ('cmaps/Adobe-Japan1.bcmap', 'pdfjs-6.4.299/cmaps/Adobe-Japan1.bcmap'),
    ('standard_fonts/FoxitSans.pfb', 'pdfjs-6.4.299/standard_fonts/FoxitSans.pfb'),
    ('wasm/openjpeg.wasm', 'pdfjs-6.4.299/wasm/openjpeg.wasm'),
    ('build/pdf.worker.min.mjs', 'assets/pdf.worker.min-HASH123.js')])
def test_pdfjs_resources_require_exact_version_and_bytes(tmp_path, resource, asset):
    (tmp_path / 'package.json').write_text('{"version":"6.4.299"}')
    path = tmp_path / resource
    path.parent.mkdir(parents=True)
    path.write_bytes(b'pinned upstream bytes')
    name = 'frontend/dist/' + asset
    p.audit_asset(name, path.read_bytes(), tmp_path)
    p.audit_asset(name + '.gz', gzip.compress(path.read_bytes()), tmp_path)
    with pytest.raises(ValueError, match='bytes differ'):
        p.audit_asset(name, b'changed payload', tmp_path)
    (tmp_path / 'package.json').write_text('{"version":"6.4.298"}')
    with pytest.raises(ValueError, match='version mismatch'):
        p.audit_asset(name, path.read_bytes(), tmp_path)


@pytest.mark.parametrize('name', ['pdfjs-6.4.299/other.wasm', 'pdfjs-6.4.298/wasm/x.wasm',
    'assets/other.mjs', 'pdfjs-6.4.299/cmaps/../x.bcmap'])
def test_pdfjs_exception_is_not_general_binary_allowlist(tmp_path, name):
    with pytest.raises(ValueError):
        p.audit_asset('frontend/dist/' + name, b'unknown', tmp_path)


def test_strict_clean_gate_no_previous_skill_exception():
    p.require_clean_tracked(lambda *_: b'')
    for status in (b' M .agents/skills/dev-builder/SKILL.md', b'M  backend/app/main.py', b' D file.py'):
        with pytest.raises(ValueError, match='Commit all tracked'):
            p.require_clean_tracked(lambda *_: status)


def test_archive_hash_readback_detects_tampering(package_files):
    raw = p.m.archive_bytes(package_files)
    p.verify_archive(raw, package_files)
    with pytest.raises(ValueError, match='hash mismatch'):
        p.verify_archive(raw, {**package_files, 'frontend/dist/assets/main.js': b'changed'})
    with pytest.raises(ValueError, match='member set'):
        p.verify_archive(raw, {**package_files, 'extra.py': b'extra'})
    with pytest.raises(ValueError, match='Unsafe'):
        p.m.archive_bytes({'../outside.py': b'bad'})


def test_build_requires_clean_tree_before_review(monkeypatch, tmp_path):
    monkeypatch.setattr(p.m.common, 'git', lambda *_: b' M tracked.py')
    monkeypatch.setattr(p.m.common, 'reviewed_status', lambda *_: pytest.fail('must reject dirty sources first'))
    with pytest.raises(ValueError, match='Commit all tracked'):
        p.build(tmp_path)


def test_packaged_maintenance_commands_have_complete_import_dependencies(tmp_path):
    import subprocess
    import sys

    source = Path(__file__).resolve().parents[1] / 'maintenance'
    for name in p.MAINTENANCE:
        (tmp_path / name).write_bytes((source / name).read_bytes())
    for command in ('audit-business-members.py', 'reconcile-business-members.py'):
        result = subprocess.run([sys.executable, str(tmp_path / command), '--help'],
                                cwd=tmp_path, capture_output=True)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        assert b'--database-url-env' in result.stdout


def test_build_records_review_migrations_and_byte_hashes(monkeypatch, tmp_path, package_files):
    import hashlib
    import tarfile

    sources = {}
    for name, data in package_files.items():
        target_name = name if name.startswith('scripts/') else p.APP + name
        target = tmp_path / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if not name.startswith('frontend/dist/'):
            sources[target_name] = data
    for helper in ('package-overseas.py', 'package-management.py', 'package-delivery.py'):
        sources['scripts/release/' + helper] = b'# committed helper'
    commit = 'abcdef0123456789abcdef0123456789abcdef0123'

    def git(_repo, *args):
        if args[0] == 'status':
            return b''
        if args[0] == 'rev-parse':
            return commit.encode()
        if args[0] == 'ls-files':
            return ('\0'.join(sources) + '\0').encode()
        if args[0] == 'show':
            return sources[args[1].split(':', 1)[1]]
        pytest.fail('Unexpected git call: ' + repr(args))

    monkeypatch.setattr(p.m.common, 'git', git)
    monkeypatch.setattr(p.m.common, 'reviewed_status', lambda *_: {'currentId': 'reviewed-candidate', 'approved': True})
    audit = p.build(tmp_path)
    output = tmp_path / 'output/release/overseas-20261014-abcdef0'
    raw = (output / 'release.tar.gz').read_bytes()
    assert audit['sha256'] == hashlib.sha256(raw).hexdigest()
    assert audit['archiveVerified'] is True
    with tarfile.open(output / 'release.tar.gz', 'r:gz') as archive:
        manifest = json.load(archive.extractfile('release.json'))
        assert manifest['migration'] == '0028'
        assert manifest['overseasMigration'] == 'overseas_0014'
        assert manifest['frontendVersion'] == '0.2.31'
        assert manifest['candidateId'] == 'reviewed-candidate'
        assert manifest['commit'] == commit
        for name, digest in manifest['files'].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest
