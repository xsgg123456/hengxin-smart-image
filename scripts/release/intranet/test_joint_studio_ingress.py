"""Private gateway and post-verification release gates; no production I/O."""
import copy
import hashlib
import json
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

import engine
import joint_studio_ingress as ingress
import joint_studio_private_config as private_config
import scope_snapshot


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    nginx = tmp_path / 'nginx.conf'
    nginx.write_bytes(b'server {\n    listen 80;\n}\n')
    monkeypatch.setattr(private_config, 'NGINX_SOURCE', nginx)
    services = {'domestic-web': {'image': 'test-image', 'ports': [
        {'target': 80, 'published': '18080', 'host_ip': '127.0.0.1', 'protocol': 'tcp'}],
        'volumes': [{'type': 'bind', 'source': str(nginx), 'target': ingress.NGINX_TARGET, 'read_only': True}]}}
    for name, (module, port, _) in ingress.API.items():
        services[name] = {'image': 'test-api', 'command': ['uvicorn', module, '--host', '0.0.0.0', '--port', '8000'],
                          'ports': [{'target': 8000, 'published': port, 'host_ip': '127.0.0.1', 'protocol': 'tcp'}]}
    candidate = {'name': 'hengxin-lan', 'services': services}
    raw = json.dumps(candidate).encode()
    (tmp_path / 'compose.candidate.json').write_bytes(raw)
    (tmp_path / 'started.json').write_text('{}')
    state = {'services': {}, 'events': [], 'queues': {}, 'gated': True,
             'markers': {'workers': False, 'ingress': False}}
    digest = lambda value: hashlib.sha256(value).hexdigest()

    def write(path, value, mode=0o600, exclusive=False):
        assert mode == 0o600 and exclusive
        with Path(path).open('xb') as stream:
            stream.write(value)
        Path(path).chmod(mode)

    def compose(*args, config):
        content = json.loads(Path(config).read_bytes())
        if args[0] in ('config', 'run'):
            state['events'].append(('preflight', args[0]))
            return (tmp_path / 'nginx.private-gateway.conf').read_text() if args[0] == 'run' else ''
        names = args[5:]
        state['events'].append(('compose', names))
        for name in names:
            state['services'][name] = copy.deepcopy(content['services'][name])

    def run(args, **kwargs):
        if args[:2] == ['docker', 'inspect']:
            name = args[2].removeprefix('hengxin-lan-')
            service = state['services'][name]
            bindings = {str(item['target']) + '/tcp': [{'HostIp': item['host_ip'], 'HostPort': item['published']}]
                        for item in service.get('ports', [])}
            mounts = [{'Destination': item['target'], 'Source': item['source'], 'RW': not item.get('read_only')}
                      for item in service.get('volumes', [])]
            return json.dumps([{'Name': '/hengxin-lan-' + name,
                'Config': {'Cmd': service.get('command'), 'Labels': {'com.docker.compose.project': 'hengxin-lan',
                                                                      'com.docker.compose.service': name}},
                'State': {'Running': service.get('running', True)}, 'Mounts': mounts,
                'HostConfig': {'NetworkMode': 'bridge', 'PortBindings': bindings},
                'NetworkSettings': {'Ports': bindings}}])
        if args[-2:] == ['nginx', '-T']:
            return (tmp_path / 'nginx.private-gateway.conf').read_text()
        assert args[:3] == ['docker', 'exec', 'hengxin-lan-domestic-web']
        return '<html>verified</html>'

    def app(action, names, candidate=False):
        state['events'].append((action, tuple(names)))
        for name in names:
            if action == 'stop' and name in state['services']:
                state['services'][name]['running'] = False
            elif action == 'up':
                state['services'][name] = copy.deepcopy(services[name])

    u = SimpleNamespace(WORK=tmp_path, safe=lambda path: None, digest=digest, write=write,
                        compose=compose, run=run, health=lambda *args, **kwargs: None,
                        ENTRIES=('domestic-web', *ingress.API), WORKERS=('domestic', 'overseas', 'image'))
    current = {'ctx': {}, 'sockets': [], 'paused': list(u.WORKERS)}
    monkeypatch.setattr(engine, '_read', lambda name: {'candidate': digest(raw)})
    monkeypatch.setattr(engine, '_load_state', lambda baseline: current)
    monkeypatch.setattr(engine, '_save', lambda *args, **kwargs: None)
    monkeypatch.setattr(ingress.paths, 'gate_state', lambda u, name: state['markers'][name])
    def set_gate(u, name, opened):
        state['events'].append(('gate', name, opened))
        state['markers'][name] = opened
    monkeypatch.setattr(ingress.paths, 'set_gate', set_gate)
    u.contexts = lambda: current['ctx']
    gate = ingress.PrivateIngress(u, app, lambda *args, **kwargs: state['events'].append('health'),
                                  lambda value: state.update(gated=False))
    return gate, state, candidate, current


def test_candidate_has_private_listeners_and_rejects_changed_configuration(gateway):
    gate, state, candidate, _ = gateway
    gate.stage(gate.u.ENTRIES)
    private = json.loads((gate.u.WORK / 'compose.private-gateway.json').read_bytes())
    web = private['services']['domestic-web']
    assert web['ports'] == []
    assert web['volumes'][0]['source'] == str(gate.u.WORK / 'nginx.private-gateway.conf')
    assert b'if ($remote_addr != 127.0.0.1) { return 503; }' in (gate.u.WORK / 'nginx.private-gateway.conf').read_bytes()
    web['ports'] = candidate['services']['domestic-web']['ports']
    web['volumes'][0]['source'] = candidate['services']['domestic-web']['volumes'][0]['source']
    for name in ingress.API:
        assert private['services'][name]['ports'] == []
        assert private['services'][name]['command'][3] == '127.0.0.1'
        private['services'][name]['ports'] = candidate['services'][name]['ports']
        private['services'][name]['command'][3] = '0.0.0.0'
    assert private == candidate
    gate.stage(gate.u.ENTRIES)
    (gate.u.WORK / 'compose.private-gateway.json').write_text('{}')
    with pytest.raises(RuntimeError, match='configuration changed'):
        gate.stage()
    assert all(not item.get('ports') for item in state['services'].values())


def test_preflight_checks_private_configuration_without_starting_services(gateway):
    gate, state, _, _ = gateway
    source = private_config.NGINX_SOURCE
    gate.preflight({'configs': {str(source): hashlib.sha256(source.read_bytes()).hexdigest()}})
    assert state['services'] == {}
    assert state['events'] == [('preflight', 'config'), ('preflight', 'run')]


def test_private_probe_refuses_exposed_gateway_api_and_wrong_bytes(gateway):
    gate, state, candidate, _ = gateway
    gate.stage(gate.u.ENTRIES)
    manifest = {'files': {'frontend/index.html': hashlib.sha256(b'<html>verified</html>').hexdigest()}}
    gate.verify_frontend('domestic', manifest)
    with pytest.raises(RuntimeError, match='differs'):
        gate.verify_frontend('domestic', {'files': {'frontend/index.html': 'incorrect'}})
    state['services']['domestic-web']['ports'] = candidate['services']['domestic-web']['ports']
    with pytest.raises(RuntimeError, match='published host port'):
        gate.verify_frontend('domestic', manifest)
    state['services']['domestic-api']['command'][3] = '0.0.0.0'
    with pytest.raises(RuntimeError, match='listener isolation'):
        gate.assert_api('domestic-api', private=True)


def test_nginx_preflight_rejects_other_servers_or_spoofable_real_ip():
    valid = 'server {\n if ($remote_addr != 127.0.0.1) { return 503; }\n}'
    ingress.verify_nginx_dump(valid)
    with pytest.raises(RuntimeError, match='virtual host'):
        ingress.verify_nginx_dump(valid + '\nserver { listen 81; }')
    with pytest.raises(RuntimeError, match='real-IP'):
        ingress.verify_nginx_dump(valid + '\nreal_ip_header X-Forwarded-For;')


def test_candidate_start_gates_credentials_before_other_services(gateway, monkeypatch, tmp_path):
    gate, state, _, current = gateway
    monkeypatch.setattr(gate, 'health', lambda *args, **kwargs: state['events'].append('private-health'))
    endpoint = tmp_path / 'candidate-credentials.sock'
    sock = socket.socket(socket.AF_UNIX)
    try:
        sock.bind(str(endpoint))
        endpoint.chmod(0)
        current['sockets'] = [(str(endpoint), endpoint.lstat().st_ino + 1, 0o600)]
        gate.u.ACCOUNT_SOCKETS = (str(endpoint),)
        gate.u.gate_accounts = lambda records: state['events'].append('credentials-gated')
        monkeypatch.setattr(ingress.credentials, 'prepare', lambda *args: state['events'].append('stale-checked'))
        def start(_, after_credentials, before_credentials):
            before_credentials()
            state['events'].append('credentials-started')
            after_credentials()
            gate.app_command('up', gate.u.ENTRIES)
            state['events'].append('started-private')
        gate.start(start, current['ctx'])
        assert all(not item.get('ports') for item in state['services'].values()) and gate.paused
        assert state['events'].index('credentials-gated') < state['events'].index('started-private')
        assert current['sockets'][-1] == (str(endpoint), endpoint.lstat().st_ino, 0o600)
    finally:
        sock.close()


def test_private_snapshot_normalizes_only_validated_gateway_config(gateway):
    gate, _, _, _ = gateway
    gate.stage(gate.u.ENTRIES)
    source = private_config.NGINX_SOURCE
    private = gate.u.WORK / 'nginx.private-gateway.conf'
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    after = {'configs': {str(private): digest(private), '/unchanged': 'same'}}
    before = {'configs': {str(source): digest(source)}}
    normalized = gate.normalize(after, before)
    assert normalized['configs'] == {str(source): digest(source), '/unchanged': 'same'}
    source.write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='changed'):
        gate.normalize(after, before)


@pytest.mark.skipif(not hasattr(socket, 'AF_UNIX'), reason='requires Unix domain sockets')
def test_credential_gate_checks_real_socket_identity_and_mode(gateway, tmp_path):
    gate, _, _, _ = gateway
    endpoint = tmp_path / 'credential.sock'
    sock = socket.socket(socket.AF_UNIX)
    try:
        sock.bind(str(endpoint))
        endpoint.chmod(0o600)
        state = {'sockets': [(str(endpoint), endpoint.lstat().st_ino, 0o600)]}
        gate.u.ACCOUNT_SOCKETS = (str(endpoint),)
        endpoint.chmod(0)
        gate.socket_modes(state, gated=True)
        with pytest.raises(RuntimeError, match='gate changed'):
            gate.socket_modes(state, gated=False)
        endpoint.chmod(0o600)
        gate.socket_modes(state, gated=False)
        state['sockets'][0] = (str(endpoint), endpoint.lstat().st_ino + 1, 0o600)
        with pytest.raises(RuntimeError, match='gate changed'):
            gate.socket_modes(state, gated=False)
    finally:
        sock.close()


def test_readiness_commands_cannot_exceed_the_shared_deadline(gateway, monkeypatch):
    gate, _, _, _ = gateway
    calls = []
    gate.u.run = lambda args, **kwargs: calls.append(kwargs['timeout'])
    monkeypatch.setattr(ingress.time, 'monotonic', lambda: 10.0)
    with gate.bounded(12.0):
        gate.u.run(['probe'], timeout=60)
        assert calls == [2.0]
    with gate.bounded(10.0), pytest.raises(RuntimeError, match='deadline'):
        gate.u.run(['probe'])


def test_open_public_checks_formal_route_before_opening_workers_and_ingress(gateway, monkeypatch):
    gate, state, _, _ = gateway
    gate.stage(gate.u.ENTRIES)
    monkeypatch.setattr(gate, 'socket_modes', lambda _, gated: state['events'].append(('socket-check', gated)))
    monkeypatch.setattr(ingress.time, 'sleep', lambda _: None)
    monkeypatch.setattr(ingress.urllib.request, 'urlopen', lambda *args, **kwargs: DummyResponse())
    def capture(*args, **kwargs):
        assert state['markers'] == {'workers': False, 'ingress': False}
        state['events'].append('formal-snapshot')
        return {'verified': True}
    monkeypatch.setattr(scope_snapshot, 'capture', capture)
    gate.open_public({'verified': True})
    assert state['gated'] is False and state['services']['domestic-web']['ports']
    assert state['events'].index(('socket-check', True)) < state['events'].index(('up', tuple(ingress.API)))
    assert state['events'].index('formal-snapshot') < state['events'].index(('gate', 'workers', True))
    assert state['events'].index(('gate', 'workers', True)) < state['events'].index('health')
    assert state['events'][-1] == ('gate', 'ingress', True)
    assert not gate.paused


class DummyResponse:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): pass


def test_seal_stops_all_entries_before_draining(gateway, monkeypatch):
    gate, state, _, _ = gateway
    gate.stage(gate.u.ENTRIES)
    state['events'].clear()
    state['markers'].update(workers=True, ingress=True)
    gate.original_quiesce = lambda _: state['events'].append('drained-and-gated')
    monkeypatch.setattr(ingress.forward, 'stop_existing', lambda _: state['events'].append('background-stopped'))
    gate.seal()
    assert all(not item.get('running', True) for item in state['services'].values()) and gate.paused
    assert state['events'] == [('gate', 'ingress', False), ('stop', gate.u.ENTRIES), 'drained-and-gated',
                               'background-stopped', ('gate', 'workers', False)]
