import io
import json
from pathlib import Path
import sys
import tarfile
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import operations
import snapshot
import stage


def archive(path, files, special=None):
    data = dict(files)
    data['release-manifest.json'] = json.dumps({'commit': 'a'*40,
        'files': {n: snapshot.sha(v) for n, v in files.items()}}).encode()
    with tarfile.open(path, 'w:gz') as tar:
        for name, raw in data.items():
            item = tarfile.TarInfo(name)
            item.size = len(raw)
            tar.addfile(item, io.BytesIO(raw))
        if special:
            tar.addfile(special)


@pytest.fixture
def fake(tmp_path):
    def write(path, data, mode=0o600, exclusive=False):
        with path.open('xb' if exclusive else 'wb') as stream:
            stream.write(data)
        path.chmod(mode)
    return SimpleNamespace(safe=lambda *a, **k: None, write=write,
                           RELEASE=tmp_path/'release', validate_release=lambda: 'manifest')


def test_stage_validates_and_refuses_overwrite(tmp_path, fake, monkeypatch):
    monkeypatch.setattr(stage, 'RELEASES', tmp_path)
    package = tmp_path/'package.tgz'
    archive(package, {'backend/app/execution/office_render.py': b'render', 'frontend/index.html': b'html'})
    root = stage.unpack(package, 'candidate', fake)
    assert (root/'frontend/index.html').read_bytes() == b'html'
    with pytest.raises(RuntimeError, match='already exists'):
        stage.unpack(package, 'candidate', fake)


def test_stage_refuses_reusing_name_after_old_directory_was_cleaned(tmp_path, fake, monkeypatch):
    monkeypatch.setattr(stage, 'RELEASES', tmp_path)
    path = tmp_path/'previously-used'
    assert not path.exists()
    with pytest.raises(RuntimeError, match='already used'):
        stage.unpack(tmp_path/'not-even-opened.tar.gz', path.name, fake, used={str(path)})
    assert not path.exists()


def test_stage_cli_passes_locked_history_to_unpack(tmp_path, fake, monkeypatch):
    import release
    store = release.retention_store(tmp_path/'state')
    monkeypatch.setattr(stage.socket, 'gethostname', lambda: 'hengxin-ai-245')
    monkeypatch.setattr(stage.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(stage.engine, 'u', fake)
    monkeypatch.setattr(stage, 'retention_store', lambda *a: store)
    monkeypatch.setattr(stage.Release, 'load', lambda self: {'current': {}})
    def history(*args):
        with pytest.raises(OSError):
            with store.locked():
                pytest.fail('stage must hold lock')
        return {'old-source'}
    monkeypatch.setattr(stage.cleanup_history, 'known', history)
    seen = []
    monkeypatch.setattr(stage, 'unpack', lambda *a, **k: seen.append(k['used']))
    monkeypatch.setattr(sys, 'argv', ['stage.py', 'input.tar.gz', '--name', 'new'])
    stage.main()
    assert seen == [{'old-source'}]


@pytest.mark.parametrize('member', ['../escape', '/etc/escape', 'frontend/../../escape', 'frontend\\escape'])
def test_stage_rejects_traversal_before_writing(tmp_path, fake, monkeypatch, member):
    monkeypatch.setattr(stage, 'RELEASES', tmp_path)
    package = tmp_path/'package.tgz'
    archive(package, {member: b'invalid'})
    with pytest.raises(RuntimeError):
        stage.unpack(package, 'candidate', fake)
    assert not (tmp_path/'candidate').exists()


def test_stage_rejects_symlink(tmp_path, fake, monkeypatch):
    monkeypatch.setattr(stage, 'RELEASES', tmp_path)
    package = tmp_path/'package.tgz'
    link = tarfile.TarInfo('frontend/link')
    link.type, link.linkname = tarfile.SYMTYPE, '/etc'
    archive(package, {}, link)
    with pytest.raises(RuntimeError, match='unsafe'):
        stage.unpack(package, 'candidate', fake)


def web(tmp_path, fake):
    work = tmp_path/'transaction'
    work.mkdir()
    compose = tmp_path/'compose.json'
    compose.write_bytes(b'original')
    (work/'web-before.json').write_bytes(b'original')
    (work/'compose.candidate.json').write_bytes(b'new')
    (work/'web-prepared.json').write_text(json.dumps({
        'before': snapshot.sha(b'original'), 'candidate': snapshot.sha(b'new'), 'manifest': 'manifest'}))
    fake.WORK, fake.COMPOSE = work, compose
    return work, compose


def test_web_switch_only_changes_web_and_recovers_once(tmp_path, fake):
    work, compose = web(tmp_path, fake)
    calls = []
    fake.app_command = lambda action, names: calls.append((action, names))
    operations.apply_web(fake)
    assert compose.read_bytes() == b'new'
    assert calls == [('up', ('domestic-web',))]
    operations.recover_web(fake)
    operations.recover_web(fake)
    assert compose.read_bytes() == b'original'
    assert len(calls) == 2


def test_web_start_failure_restores_original(tmp_path, fake):
    work, compose = web(tmp_path, fake)
    calls = []
    def start(action, names):
        calls.append(names)
        if len(calls) == 1:
            raise RuntimeError('web startup failed')
    fake.app_command = start
    with pytest.raises(RuntimeError, match='startup failed'):
        operations.apply_web(fake)
    assert compose.read_bytes() == b'original'
    assert (work/'rolled-back.json').exists()
    assert calls == [('domestic-web',), ('domestic-web',)]


def test_interrupted_web_requires_explicit_recovery(tmp_path, fake):
    work, compose = web(tmp_path, fake)
    (work/'started.json').write_text('{}')
    fake.app_command = lambda *a: pytest.fail('must not restart')
    with pytest.raises(RuntimeError, match='Interrupted'):
        operations.apply_web(fake)
