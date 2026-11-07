"""Package integrity and fail-closed rollback without production access."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_package_rejects_changed_or_extra_source(tmp_path):
    scope = module('overseas-light-runtime')
    files = {('api/' + name): b'code\n' for name in scope.r.FILES}
    files.update({('tests/' + name): b'test\n' for name in ('conftest.py', *scope.TESTS)})
    files.update({('scripts/release/' + name + '.py'): b'helper\n' for name in scope.HELPERS})
    files.update({'frontend/package.json': b'{"version":"0.2.67"}',
                  'frontend/dist/index.html': b'<script type="module" src="/assets/app.js"></script>',
                  'frontend/dist/assets/app.js': b'console.log(1)'})
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    manifest = {'release': 'overseas-light-20261107-abcdef0', 'version': '0.2.67', 'commit': 'a' * 40,
                'candidateId': 'b' * 64, 'api': {'image': scope.BASE_IMAGE,
                'files': {n: {'baseline': 'c' * 64, 'sha256': sha(files['api/' + n])} for n in scope.r.FILES}},
                'files': {n: sha(body) for n, body in files.items()}}
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (tmp_path / 'release.json').write_text(json.dumps(manifest))
    assert scope.verify_package(tmp_path) == manifest
    first = tmp_path / ('api/' + next(iter(scope.r.FILES)))
    first.write_bytes(b'tampered')
    with pytest.raises(RuntimeError, match='checksum'):
        scope.verify_package(tmp_path)
    first.write_bytes(b'code\n')
    (tmp_path / 'extra').write_text('unexpected')
    with pytest.raises(RuntimeError, match='Unmanifested'):
        scope.verify_package(tmp_path)
    (tmp_path / 'extra').unlink()
    (tmp_path / 'frontend/dist/index.html').write_text('html')
    manifest['files']['frontend/dist/index.html'] = sha(b'html')
    (tmp_path / 'release.json').write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match='entry missing JavaScript'):
        scope.verify_package(tmp_path)


def test_failed_frontend_switch_restores_api_before_reopening(tmp_path, monkeypatch):
    deploy = module('overseas-light-deploy')
    events = []
    overlay = tmp_path / 'old-overlay.json'
    overlay.write_text('original')
    data = {'oldId': 'old', 'oldImage': 'sha256:old', 'image': 'sha256:new', 'compose': {},
            'protected': {}, 'manifest': 'm', 'oldOverlayHash': deploy.r.digest(overlay)}
    monkeypatch.setattr(deploy, 'state', lambda *_args, **_kwargs: (data, tmp_path))
    monkeypatch.setattr(deploy.r, 'inspect', lambda: {'Id': 'old', 'Image': 'sha256:old', 'State': {'Running': True}})
    monkeypatch.setattr(deploy.gate, 'set_gate', lambda _w, _d, closed: events.append('closed' if closed else 'opened'))
    monkeypatch.setattr(deploy.r, 'run', lambda *args, **kwargs: events.append('stop'))
    monkeypatch.setattr(deploy.r.a, 'compose', lambda _d, *_args, overlay: events.append(Path(overlay).name))
    monkeypatch.setattr(deploy, 'verify_api', lambda *_args: {'readOnly': True})
    monkeypatch.setattr(deploy.r, 'unchanged', lambda *_args: None)
    monkeypatch.setattr(deploy, 'ready', lambda *_args: None)

    def fail_front(_source, _app, backup):
        backup.mkdir()
        (backup / 'COMPLETE.json').write_text('{}')
        raise RuntimeError('frontend failed')

    monkeypatch.setattr(deploy.frontend, 'deploy', fail_front)
    monkeypatch.setattr(deploy.frontend, 'rollback', lambda *_args: events.append('frontend-rollback'))
    with pytest.raises(RuntimeError, match='frontend failed'):
        deploy.deploy(tmp_path)
    assert events == ['closed', 'stop', 'api-overlay.json', 'closed', 'frontend-rollback', 'old-overlay.json', 'opened']


def test_unconfirmed_stop_does_not_replace_or_reopen(tmp_path, monkeypatch):
    deploy = module('overseas-light-deploy')
    events = []
    overlay = tmp_path / 'old-overlay.json'
    overlay.write_text('original')
    data = {'oldId': 'old', 'oldImage': 'sha256:old', 'image': 'sha256:new', 'compose': {},
            'protected': {}, 'manifest': 'm', 'oldOverlayHash': deploy.r.digest(overlay)}
    monkeypatch.setattr(deploy, 'state', lambda *_args, **_kwargs: (data, tmp_path))
    monkeypatch.setattr(deploy.r, 'inspect', lambda: {'Id': 'old', 'State': {'Running': True}})
    monkeypatch.setattr(deploy.gate, 'set_gate', lambda _w, _d, closed: events.append('closed' if closed else 'opened'))
    monkeypatch.setattr(deploy.r, 'run', lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError('stop pending')))
    monkeypatch.setattr(deploy.r.a, 'compose', lambda *_a, **_k: events.append('compose'))
    with pytest.raises(TimeoutError):
        deploy.deploy(tmp_path)
    assert events == ['closed']
