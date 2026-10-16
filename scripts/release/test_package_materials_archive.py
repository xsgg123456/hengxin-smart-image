import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import pytest

spec = importlib.util.spec_from_file_location('studio_package', Path(__file__).with_name('package-materials-archive.py'))
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


def files():
    values = dict.fromkeys(p.REQUIRED, b'')
    values.update({'frontend/package.json': b'{"version":"0.2.39"}',
        'frontend/dist/index.html': b'<script src="/assets/main.js"></script>',
        'frontend/dist/assets/main.js': b'console.log(1)'})
    return values


def test_required_allowlist_and_version():
    values = files(); p.validate(values)
    for name in p.REQUIRED:
        assert p.selected(name if name.startswith('scripts/') else p.p.APP + name) == name or name.startswith('frontend/dist/')
        with pytest.raises(ValueError, match='Missing required'): p.validate({k: v for k, v in values.items() if k != name})
    with pytest.raises(ValueError, match='version'): p.validate({**values, 'frontend/package.json': b'{"version":"0.2.37"}'})
    for path in ('scripts/release/package-materials-archive.py', 'scripts/release/domestic-deploy.py',
                 'hengxin-smart-image/backend/.env', 'hengxin-smart-image/backend/app/../private.py'):
        assert p.selected(path) is None


def test_real_selected_sources_privacy():
    repo = Path(__file__).resolve().parents[2]
    paths = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=repo, text=True).split('\0')
    for path in paths:
        name = p.selected(path)
        if name: p.p.m.common.privacy_check(name, p.p.m.common.normalized((repo / path).read_bytes()))


def test_archive_records_current_schema_date_and_complete_hashes(tmp_path, monkeypatch):
    sources = {}
    for name, body in files().items():
        tracked = name if name.startswith('scripts/') else p.p.APP + name
        local = tmp_path / tracked; local.parent.mkdir(parents=True, exist_ok=True); local.write_bytes(body)
        if not name.startswith('frontend/dist/'): sources[tracked] = body
    sources.update({'scripts/release/' + name: b'local helper' for name in p.p.PACKAGING_HELPERS})
    commit = 'abcdef0123456789abcdef0123456789abcdef0123'
    def git(_repo, *args):
        if args[0] == 'status': return b''
        if args[0] == 'rev-parse': return commit.encode()
        if args[0] == 'ls-files': return ('\0'.join(sources) + '\0').encode()
        if args[0] == 'show': return sources[args[1].split(':', 1)[1]]
        pytest.fail(repr(args))
    monkeypatch.setattr(p.p.m.common, 'git', git)
    monkeypatch.setattr(p.p.m.common, 'reviewed_status', lambda *_: {'currentId': 'reviewed'})
    audit = p.build(tmp_path)
    path = tmp_path / 'output/release/overseas-20261016-abcdef0/release.tar.gz'
    assert audit['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    with tarfile.open(path, 'r:gz') as archive:
        manifest = json.load(archive.extractfile('release.json'))
        assert (manifest['migration'], manifest['overseasMigration'], manifest['frontendVersion']) == ('0029', 'overseas_0017', '0.2.39')
        assert manifest['candidateId'] == 'reviewed'
        assert p.REQUIRED <= manifest['files'].keys()
        for name, digest in manifest['files'].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest
    old_spec = importlib.util.spec_from_file_location('legacy_package', Path(__file__).with_name('package-overseas.py'))
    old = importlib.util.module_from_spec(old_spec); old_spec.loader.exec_module(old)
    assert (old.VERSION, old.DOMESTIC_MIGRATION, old.RELEASE_PREFIX) == ('0.2.36', '0028', 'overseas-20261015-')
