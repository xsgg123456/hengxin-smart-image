import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile

import pytest

spec = importlib.util.spec_from_file_location('domestic_package', Path(__file__).with_name('package-domestic.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


@pytest.fixture
def files():
    values = {name: b'' for name in p.REQUIRED}
    values['frontend/package.json'] = json.dumps({'version': p.VERSION}).encode()
    values['frontend/dist/index.html'] = b'<script src="/assets/main.js"></script>'
    values['frontend/dist/assets/main.js'] = b'console.log(1)'
    return values


def test_domestic_required_files_and_version(files):
    p.validate(files)
    for name in p.REQUIRED:
        with pytest.raises(ValueError, match='Missing required'):
            p.validate({k: v for k, v in files.items() if k != name})
    with pytest.raises(ValueError, match='version'):
        p.validate({**files, 'frontend/package.json': b'{"version":"0.2.36"}'})
    with pytest.raises(ValueError, match='Missing frontend'):
        p.validate({k: v for k, v in files.items() if k != 'frontend/dist/assets/main.js'})


def test_explicit_domestic_allowlist():
    for name in p.SCRIPTS:
        assert p.selected('scripts/release/' + name)
    for name in p.HELPERS:
        assert p.selected('scripts/release/' + name) is None
    for name in p.EXACT:
        assert p.selected(p.APP + name) == name
    for name in ('scripts/release/domestic-unknown.py', 'scripts/release/domestic.env',
                 p.APP + 'infra/private.service', p.APP + 'backend/app/../secrets.py'):
        assert p.selected(name) is None


def test_packaged_manifest_is_independent_of_overseas_version(monkeypatch, tmp_path, files):
    sources = {}
    for name, body in files.items():
        tracked = name if name.startswith('scripts/') else p.APP + name
        local = tmp_path / tracked
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(body)
        if not name.startswith('frontend/dist/'):
            sources[tracked] = body
    commit = 'abcdef0123456789abcdef0123456789abcdef0123'
    # Local packaging helpers must be committed, but are not server runtime files.
    sources.update({'scripts/release/' + name: b'local packaging helper' for name in p.HELPERS})

    def git(_repo, *args):
        if args[0] == 'status':
            return b''
        if args[0] == 'rev-parse':
            return commit.encode()
        if args[0] == 'ls-files':
            return ('\0'.join(sources) + '\0').encode()
        if args[0] == 'show':
            return sources[args[1].split(':', 1)[1]]
        pytest.fail(repr(args))

    monkeypatch.setattr(p.p.m.common, 'git', git)
    monkeypatch.setattr(p.p.m.common, 'reviewed_status', lambda *_: {'currentId': 'reviewed'})
    audit = p.build(tmp_path)
    path = tmp_path / 'output/release/domestic-20261015-abcdef0/release.tar.gz'
    assert audit['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    with tarfile.open(path, 'r:gz') as archive:
        manifest = json.load(archive.extractfile('release.json'))
        assert manifest['migration'] == '0029'
        assert manifest['overseasMigration'] == 'overseas_0016'
        assert manifest['frontendVersion'] == '0.2.37'
        assert manifest['candidateId'] == 'reviewed'
        assert p.REQUIRED <= manifest['files'].keys()
        assert not {'scripts/release/' + name for name in p.HELPERS} & manifest['files'].keys()
        for name, digest in manifest['files'].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest
    assert p.p.VERSION == '0.2.36', 'Shared overseas packager must not be mutated'


def test_dirty_source_rejected_before_review(monkeypatch, tmp_path):
    monkeypatch.setattr(p.p.m.common, 'git', lambda *_: b' M tracked.py')
    monkeypatch.setattr(p.p.m.common, 'reviewed_status', lambda *_: pytest.fail('dirty input'))
    with pytest.raises(ValueError, match='Commit all tracked'):
        p.build(tmp_path)


def test_actual_selected_source_contents_pass_privacy_scan():
    """Audit real source bytes, including newly added files, rather than empty fixtures."""
    repo = Path(__file__).resolve().parents[2]
    paths = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'],
                                    cwd=repo, text=True).split('\0')
    checked = set()
    for path in paths:
        name = p.selected(path)
        if name:
            p.p.m.common.privacy_check(name, p.p.m.common.normalized((repo / path).read_bytes()))
            checked.add(name)
    assert 'scripts/release/domestic-deploy.py' in checked
    assert 'backend/app/modules/api_image_edits/deletion.py' in checked
    assert not {'scripts/release/' + name for name in p.HELPERS} & checked
