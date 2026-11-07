"""Release failure recovery and protected service checks."""
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def isolated_module(tmp_path, monkeypatch):
    result = module('overseas-light-deploy')
    monkeypatch.setattr(result.r.a, 'APP', tmp_path / 'isolated-app')
    monkeypatch.setattr(result.front, 'protect_publication_directories', lambda *_args: nullcontext())
    return result


def test_failed_frontend_switch_restores_api_before_reopening(tmp_path, monkeypatch):
    deploy = isolated_module(tmp_path, monkeypatch)
    events = []
    overlay = tmp_path / 'old-overlay.json'
    overlay.write_text('original')
    data = {'oldId': 'old', 'oldImage': 'sha256:old', 'image': 'sha256:new', 'compose': {},
            'protected': {}, 'manifest': 'm', 'oldOverlayHash': deploy.r.digest(overlay)}
    monkeypatch.setattr(deploy, 'state', lambda *_args, **_kwargs: (data, tmp_path))
    monkeypatch.setattr(deploy, 'check_frontend_collisions', lambda *_args: None)
    monkeypatch.setattr(deploy, 'verify_web_root', lambda *_args: None)
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

    monkeypatch.setattr(deploy, 'install_frontend', fail_front)
    monkeypatch.setattr(deploy.frontend, 'rollback', lambda *_args: events.append('frontend-rollback'))
    with pytest.raises(RuntimeError, match='frontend failed'):
        deploy.deploy(tmp_path)
    assert events == ['closed', 'stop', 'api-overlay.json', 'closed', 'frontend-rollback', 'old-overlay.json', 'opened']


def test_failed_frontend_rollback_does_not_prevent_old_api_restore(tmp_path, monkeypatch):
    deploy = isolated_module(tmp_path, monkeypatch)
    events = []
    overlay = tmp_path / 'old-overlay.json'
    overlay.write_text('original')
    data = {'oldId': 'old', 'oldImage': 'sha256:old', 'image': 'sha256:new', 'compose': {},
            'protected': {}, 'manifest': 'm', 'oldOverlayHash': deploy.r.digest(overlay)}
    monkeypatch.setattr(deploy, 'state', lambda *_args, **_kwargs: (data, tmp_path))
    monkeypatch.setattr(deploy, 'check_frontend_collisions', lambda *_args: None)
    monkeypatch.setattr(deploy, 'verify_web_root', lambda *_args: None)
    monkeypatch.setattr(deploy.r, 'inspect', lambda: {'Id': 'old', 'Image': 'sha256:old', 'State': {'Running': True}})
    monkeypatch.setattr(deploy.gate, 'set_gate', lambda _w, _d, closed: events.append('closed' if closed else 'opened'))
    monkeypatch.setattr(deploy.r, 'run', lambda *_args, **_kwargs: events.append('stop'))
    monkeypatch.setattr(deploy.r.a, 'compose', lambda _d, *_args, overlay: events.append(Path(overlay).name))
    monkeypatch.setattr(deploy, 'verify_api', lambda *_args: {'readOnly': True})
    monkeypatch.setattr(deploy.r, 'unchanged', lambda *_args: None)
    monkeypatch.setattr(deploy, 'ready', lambda *_args: None)
    def fail_install(_source, _app, backup):
        backup.mkdir()
        (backup / 'COMPLETE.json').write_text('{}')
        raise RuntimeError('install failed')
    monkeypatch.setattr(deploy, 'install_frontend', fail_install)
    monkeypatch.setattr(deploy.frontend, 'rollback', lambda *_args: (_ for _ in ()).throw(OSError('rollback failed')))
    with pytest.raises(RuntimeError, match='install failed'):
        deploy.deploy(tmp_path)
    assert events == ['closed', 'stop', 'api-overlay.json', 'closed', 'old-overlay.json']
    assert json.loads((tmp_path / 'ROLLBACK_ERRORS.json').read_text())['errors'] == ['frontend: OSError']


def test_unconfirmed_stop_does_not_replace_or_reopen(tmp_path, monkeypatch):
    deploy = isolated_module(tmp_path, monkeypatch)
    events = []
    overlay = tmp_path / 'old-overlay.json'
    overlay.write_text('original')
    data = {'oldId': 'old', 'oldImage': 'sha256:old', 'image': 'sha256:new', 'compose': {},
            'protected': {}, 'manifest': 'm', 'oldOverlayHash': deploy.r.digest(overlay)}
    monkeypatch.setattr(deploy, 'state', lambda *_args, **_kwargs: (data, tmp_path))
    monkeypatch.setattr(deploy, 'check_frontend_collisions', lambda *_args: None)
    monkeypatch.setattr(deploy, 'verify_web_root', lambda *_args: None)
    monkeypatch.setattr(deploy.r, 'inspect', lambda: {'Id': 'old', 'State': {'Running': True}})
    monkeypatch.setattr(deploy.gate, 'set_gate', lambda _w, _d, closed: events.append('closed' if closed else 'opened'))
    monkeypatch.setattr(deploy.r, 'run', lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError('stop pending')))
    monkeypatch.setattr(deploy.r.a, 'compose', lambda *_a, **_k: events.append('compose'))
    with pytest.raises(TimeoutError):
        deploy.deploy(tmp_path)
    assert events == ['closed']


def test_deployment_rechecks_state_under_publication_lock(tmp_path, monkeypatch):
    from contextlib import contextmanager
    deploy = isolated_module(tmp_path, monkeypatch)
    events = []
    overlay = tmp_path / 'old-overlay.json'
    overlay.write_text('original')
    data = {'oldId': 'old', 'oldOverlayHash': deploy.r.digest(overlay)}
    @contextmanager
    def protected(*_args):
        events.append('locked')
        try:
            yield
        finally:
            events.append('unlocked')
    monkeypatch.setattr(deploy.front, 'protect_publication_directories', protected)
    monkeypatch.setattr(deploy, 'state', lambda *_args, **_kwargs: (events.append('state') or data, tmp_path))
    monkeypatch.setattr(deploy.r, 'inspect', lambda: {'Id': 'old'})
    monkeypatch.setattr(deploy, 'deploy_locked', lambda *_args: events.append('switch'))
    deploy.deploy(tmp_path)
    assert events == ['locked', 'state', 'switch', 'unlocked']


def test_rollback_checks_protected_services_before_reopening(tmp_path, monkeypatch):
    deploy = isolated_module(tmp_path, monkeypatch)
    events = []
    overlay = tmp_path / 'old-overlay.json'
    overlay.write_text('original')
    data = {'oldId': 'old', 'oldImage': 'sha256:old', 'image': 'sha256:new', 'compose': {},
            'protected': {}, 'manifest': 'm', 'oldOverlayHash': deploy.r.digest(overlay)}
    monkeypatch.setattr(deploy, 'state', lambda *_args, **_kwargs: (data, tmp_path))
    monkeypatch.setattr(deploy, 'check_frontend_collisions', lambda *_args: None)
    monkeypatch.setattr(deploy, 'verify_web_root', lambda *_args: None)
    monkeypatch.setattr(deploy.r, 'inspect', lambda: {'Id': 'old', 'Image': 'sha256:old', 'State': {'Running': True}})
    monkeypatch.setattr(deploy.gate, 'set_gate', lambda _w, _d, closed: events.append('closed' if closed else 'opened'))
    monkeypatch.setattr(deploy.r, 'run', lambda *_args, **_kwargs: events.append('stop'))
    monkeypatch.setattr(deploy.r.a, 'compose', lambda _d, *_args, overlay: events.append(Path(overlay).name))
    monkeypatch.setattr(deploy, 'verify_api', lambda *_args: {'readOnly': True})
    monkeypatch.setattr(deploy, 'ready', lambda *_args: None)
    checks = []
    def unchanged(*_args):
        checks.append('check')
        if len(checks) > 1:
            raise RuntimeError('protected service drift')
    monkeypatch.setattr(deploy.r, 'unchanged', unchanged)
    def fail_install(_source, _app, backup):
        backup.mkdir()
        (backup / 'COMPLETE.json').write_text('{}')
        raise RuntimeError('install failed')
    monkeypatch.setattr(deploy, 'install_frontend', fail_install)
    monkeypatch.setattr(deploy.frontend, 'rollback', lambda *_args: events.append('frontend-rollback'))
    with pytest.raises(RuntimeError, match='install failed'):
        deploy.deploy(tmp_path)
    assert events == ['closed', 'stop', 'api-overlay.json', 'closed', 'frontend-rollback', 'old-overlay.json']
    assert json.loads((tmp_path / 'ROLLBACK_ERRORS.json').read_text())['errors'] == ['protected: RuntimeError']
