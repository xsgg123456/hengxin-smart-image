"""Recovery accepts order-only changes, rejects semantic drift, preserves evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import codex_auth_api_semantics as s

spec = importlib.util.spec_from_file_location('api_recover', Path(__file__).with_name('codex-auth-api-recover.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def fixture(work):
    service = dict.fromkeys(s.SERVICE_KEYS)
    service.update(command=['uvicorn', 'app.overseas.main:app'], entrypoint=None,
        environment={'BUSINESS': 'overseas'}, healthcheck={'test': ['CMD', 'true'], 'interval': '10s',
        'timeout': '5s', 'retries': 3}, init=True, mem_limit='3221225472', pull_policy='never',
        networks={'edge': {'aliases': ['overseas-api']}}, restart='unless-stopped',
        ports=[{'target': 8000, 'published': '18018', 'protocol': 'tcp', 'host_ip': '127.0.0.1'}],
        volumes=[{'type': 'volume', 'source': 'execution', 'target': '/data'},
                 {'type': 'bind', 'source': '/skills', 'target': '/skills', 'read_only': True,
                  'bind': {'create_host_path': False}}])
    full = dict(services={'api': service}, volumes={'execution': {'name': 'execution-volume'}},
                networks={'edge': {'name': 'hx-overseas-edge'}})
    base = {'User': 'app', 'WorkingDir': '/app', 'Env': ['PATH=/bin', 'OLD=unchanged'], 'Labels': {}}
    data = {'paths': ['/old/compose.yaml'], 'env': '/old/runtime.env'}
    config, host, mounts, networks = s.expected(full, base, data, 'a' * 64, work)
    config['Env'] = [key + '=' + value for key, value in config['Env'].items()]
    live = dict(Config=config, HostConfig=host,
        Mounts=[dict(Destination=dest, Type=kind, Source=source, Name=source, RW=rw)
                for dest, (kind, source, rw) in mounts.items()],
        NetworkSettings={'Networks': {name: {'Aliases': list(aliases)} for name, aliases in networks.items()}},
        Id=s.NEW_ID, Image=s.NEW_IMAGE, State={'Running': True, 'Health': {'Status': 'healthy'}})
    return live, full, base, data


def test_order_only_environment_and_mount_changes_pass(tmp_path):
    live, full, base, data = fixture(tmp_path)
    live['Config']['Env'].reverse()
    live['HostConfig']['Binds'].reverse()
    live['Mounts'].reverse()
    s.verify_semantics(live, full, base, data, 'a' * 64, tmp_path)


@pytest.mark.parametrize('field', ['environment', 'duplicate-env', 'command', 'user', 'label', 'mount',
    'network', 'alias', 'port', 'restart', 'memory', 'security', 'health', 'unknown-host', 'unknown-config'])
def test_every_semantic_drift_fails(tmp_path, field):
    live, full, base, data = fixture(tmp_path)
    if field == 'environment': live['Config']['Env'][0] = 'PATH=/foreign'
    elif field == 'duplicate-env': live['Config']['Env'].append(live['Config']['Env'][0])
    elif field == 'command': live['Config']['Cmd'] = ['other']
    elif field == 'user': live['Config']['User'] = 'root'
    elif field == 'label': live['Config']['Labels']['com.docker.compose.image'] = 'foreign'
    elif field == 'mount': live['Mounts'][0]['RW'] = False
    elif field == 'network': live['NetworkSettings']['Networks']['foreign'] = {'Aliases': []}
    elif field == 'alias': next(iter(live['NetworkSettings']['Networks'].values()))['Aliases'].append('foreign')
    elif field == 'port': live['HostConfig']['PortBindings'] = {}
    elif field == 'restart': live['HostConfig']['RestartPolicy']['Name'] = 'always'
    elif field == 'memory': live['HostConfig']['Memory'] = 1
    elif field == 'security': live['HostConfig']['Privileged'] = True
    elif field == 'health': live['Config']['Healthcheck']['Retries'] = 0
    elif field == 'unknown-host': live['HostConfig']['UnknownRisk'] = True
    else: live['Config']['UnknownRisk'] = True
    with pytest.raises(RuntimeError):
        s.verify_semantics(live, full, base, data, 'a' * 64, tmp_path)


def test_recovery_preserves_failed_evidence_and_never_restarts(tmp_path, monkeypatch):
    live, full, base, data = fixture(tmp_path)
    patch = tmp_path / 'api-patch.json'
    patch.write_text('{}')
    data.update(id=s.OLD_ID, old_image=s.OLD_IMAGE, image=s.NEW_IMAGE,
        manifest=d.r.digest(patch), files={'app/example.py': {'sha256': 'b' * 64}},
        config_files={}, other={}, config='original-raw-config-digest')
    artifacts = {'api-prepared.json': data, 'api-stage.json': {'phase': 'started'},
        'API_INSTALL_TESTS_PASSED': {'manifest': data['manifest'], 'image': s.NEW_IMAGE},
        'api-overlay.json': {'services': {'api': {'image': s.NEW_IMAGE}}}}
    for name, value in artifacts.items():
        (tmp_path / name).write_text(json.dumps(value))
    original = {name: (tmp_path / name).read_bytes() for name in artifacts}
    monkeypatch.setattr(d.api, 'package', lambda _: data['files'])
    monkeypatch.setattr(d.api, 'inspect', lambda: live)
    monkeypatch.setattr(d.api, 'other_topology', lambda: {})
    monkeypatch.setattr(d.api, 'config_hash', lambda _: 'different-raw-order-digest')
    def compose(_, *args, **kwargs):
        if '--hash' in args:
            return 'api ' + ('a' * 64 if kwargs.get('override') else s.OLD_SERVICE_HASH)
        return json.dumps(full)
    monkeypatch.setattr(d.api, 'compose', compose)
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        if args[:3] == ('docker', 'image', 'inspect'): return json.dumps([{'Config': base}])
        if args[:2] == ('docker', 'exec'): return json.dumps({'app/example.py': 'b' * 64})
        return ''
    monkeypatch.setattr(d.r, 'run', run)
    d.verify(tmp_path)
    assert {name: (tmp_path / name).read_bytes() for name in artifacts} == original
    receipt = json.loads((tmp_path / 'API_RECOVERY_VERIFIED.json').read_text())
    assert receipt['originalEvidencePreserved'] and not receipt['restartedServices']
    assert receipt['originalConfigDigest'] == 'original-raw-config-digest'
    assert all(call[:2] in [('docker', 'image'), ('docker', 'exec'), ('docker', 'diff')]
               or call[0] == 'curl' for call in calls)


def test_fixed_recovery_release_rejects_unrelated_id(tmp_path, monkeypatch):
    artifacts = {'api-prepared.json': {'id': 'foreign'}, 'api-stage.json': {},
                 'api-patch.json': {}, 'API_INSTALL_TESTS_PASSED': {}, 'api-overlay.json': {}}
    for name, value in artifacts.items():
        (tmp_path / name).write_text(json.dumps(value))
    calls = []
    monkeypatch.setattr(d.r, 'run', lambda *a, **k: calls.append(a))
    with pytest.raises(RuntimeError, match='restricted'):
        d.verify(tmp_path)
    assert not calls and not (tmp_path / 'API_RECOVERY_VERIFIED.json').exists()
