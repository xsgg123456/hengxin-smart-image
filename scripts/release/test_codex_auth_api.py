"""The API patch changes only its immutable image, preserving deployment overlays."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
spec = importlib.util.spec_from_file_location('codex_auth_api', Path(__file__).with_name('codex-auth-api.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def test_api_package_rejects_extra_file(tmp_path):
    (tmp_path / 'api-patch.json').write_text(json.dumps({'files': {'app/core/config.py': {}}}))
    with pytest.raises(RuntimeError, match='exactly two'):
        d.package(tmp_path)


def live_config():
    return dict(Config={'Image': 'old', 'Hostname': 'old-id', 'Env': ['SECRET=unchanged'],
        'Cmd': ['uvicorn'], 'Labels': {'io.hengxin.project': 'smart-image',
            'com.docker.compose.config-hash': 'old', 'com.docker.compose.image': 'old'}},
        HostConfig={'ReadonlyRootfs': True}, Mounts=[{'Destination': '/data', 'RW': True}],
        NetworkSettings={'Networks': {'business': {}}})


def test_config_allows_only_image_and_dynamic_compose_identity():
    old, new = live_config(), live_config()
    new['Config'].update(Image='new', Hostname='new-id')
    new['Config']['Labels']['com.docker.compose.config-hash'] = 'new'
    new['Config']['Labels']['com.docker.compose.image'] = 'new'
    assert d.config_hash(old) == d.config_hash(new)
    assert 'SECRET' not in d.config_hash(old)


@pytest.mark.parametrize('field', ['env', 'command', 'mount', 'network', 'host'])
def test_config_rejects_other_runtime_drift(field):
    old, new = live_config(), live_config()
    if field == 'env':
        new['Config']['Env'] = ['SECRET=changed']
    elif field == 'command':
        new['Config']['Cmd'] = ['other']
    elif field == 'mount':
        new['Mounts'][0]['RW'] = False
    elif field == 'network':
        new['NetworkSettings']['Networks'] = {'foreign': {}}
    else:
        new['HostConfig']['ReadonlyRootfs'] = False
    assert d.config_hash(old) != d.config_hash(new)


def test_compose_preserves_complete_chain_and_only_starts_api(monkeypatch):
    calls = []
    monkeypatch.setattr(d.r, 'run', lambda *a, **k: calls.append(a))
    data = {'paths': ['/old/base.yaml', '/old/overlay.json'], 'env': '/old/private.env'}
    d.compose(data, 'up', '-d', '--no-deps', '--no-build', 'api', override='/new/api-overlay.json')
    assert calls == [('docker', 'compose', '-p', 'hengxin-overseas', '--env-file', '/old/private.env',
        '-f', '/old/base.yaml', '-f', '/old/overlay.json', '-f', '/new/api-overlay.json',
        'up', '-d', '--no-deps', '--no-build', 'api')]


def test_switch_refuses_original_container_drift(tmp_path, monkeypatch):
    monkeypatch.setattr(d, 'validate', lambda _: {'id': 'old'})
    monkeypatch.setattr(d, 'inspect', lambda: {'Id': 'unexpected'})
    calls = []
    monkeypatch.setattr(d, 'compose', lambda *a, **k: calls.append(a))
    with pytest.raises(RuntimeError, match='Original API drift'):
        d.switch(tmp_path)
    assert not calls and not (tmp_path / 'api-stage.json').exists()


def test_failed_post_switch_verification_never_rolls_back(tmp_path, monkeypatch):
    live = live_config()
    live.update(Id='old-id', Image='old-image')
    data = dict(id='old-id', old_image='old-image', config=d.config_hash(live), other={})
    monkeypatch.setattr(d, 'validate', lambda _: data)
    monkeypatch.setattr(d, 'inspect', lambda: live)
    monkeypatch.setattr(d, 'other_topology', lambda: {})
    calls = []
    monkeypatch.setattr(d, 'compose', lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(d, 'verify', lambda *_: (_ for _ in ()).throw(RuntimeError('unhealthy')))
    with pytest.raises(RuntimeError, match='unhealthy'):
        d.switch(tmp_path)
    assert len(calls) == 1
    assert calls[0][0][1:] == ('up', '-d', '--no-deps', '--no-build', 'api')
    assert json.loads((tmp_path / 'api-stage.json').read_text())['phase'] == 'started'


def test_missing_install_receipt_blocks_before_runtime_commands(tmp_path, monkeypatch):
    data = dict(files={}, manifest='hash', config_files={}, image='sha256:new')
    (tmp_path / 'api-prepared.json').write_text(json.dumps(data))
    (tmp_path / 'api-overlay.json').write_text(json.dumps({'services': {'api': {'image': data['image']}}}))
    monkeypatch.setattr(d, 'package', lambda _: {})
    monkeypatch.setattr(d.r, 'digest', lambda _: 'hash')
    monkeypatch.setattr(d, 'image_hashes', lambda _: {})
    calls = []
    monkeypatch.setattr(d.r, 'run', lambda *a, **k: calls.append(a))
    with pytest.raises(FileNotFoundError):
        d.switch(tmp_path)
    assert calls == []
