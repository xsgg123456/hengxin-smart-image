"""Derive a private, auditable listener configuration from the staged release."""
import json
from pathlib import Path
import re
import stat

import engine
import snapshot


API = {
    'domestic-api': ('app.main:app', '18008', '/api/v1/health/ready'),
    'overseas-api': ('app.overseas.main:app', '18018', '/api/overseas/v1/health/ready'),
    'identity-api': ('app.identity.main:app', '18012', '/api/identity/v1/config'),
}
NGINX_TARGET = '/etc/nginx/conf.d/default.conf'
NGINX_SOURCE = Path('/opt/hengxin-lan/nginx.conf')


def verify_nginx_dump(config):
    if (len(re.findall(r'(?m)^\s*server\s*\{', config)) != 1
            or config.count('if ($remote_addr != 127.0.0.1) { return 503; }') != 1
            or re.search(r'(?m)^\s*(?:real_ip_header|set_real_ip_from|real_ip_recursive)\b', config)):
        raise RuntimeError('Candidate gateway has an unexpected virtual host or real-IP rule')


def retained(u, path, payload):
    if path.exists() or path.is_symlink():
        u.safe(path)
        if stat.S_IMODE(path.stat().st_mode) != 0o600 or path.read_bytes() != payload:
            raise RuntimeError('Private gateway configuration changed')
    else:
        u.write(path, payload, mode=0o600, exclusive=True)


def nginx_source(config):
    mounts = config['services']['domestic-web'].get('volumes', [])
    matches = [item for item in mounts if isinstance(item, dict) and item.get('target') == NGINX_TARGET]
    if (len(matches) != 1 or matches[0].get('type') != 'bind' or not matches[0].get('read_only')
            or matches[0].get('source') != str(NGINX_SOURCE)):
        raise RuntimeError('Unexpected gateway configuration mount')
    return matches[0]


def stage_config(u):
    source = u.WORK / 'compose.candidate.json'
    u.safe(source)
    raw = source.read_bytes()
    if u.digest(raw) != engine._read('prepared.json')['candidate']:
        raise RuntimeError('Private gateway candidate changed')
    config = json.loads(raw)
    web = config['services']['domestic-web']
    expected = [{'target': 80, 'published': '18080', 'host_ip': '127.0.0.1', 'protocol': 'tcp'}]
    if web.get('ports') != expected or web.get('network_mode') == 'host':
        raise RuntimeError('Unexpected gateway port configuration')
    mount = nginx_source(config)
    source = Path(mount['source'])
    u.safe(source)
    original = source.read_bytes()
    if (original.count(b'server {') != 1 or not original.lstrip().startswith(b'server {')
            or re.search(rb'(?m)^\s*(?:real_ip_header|set_real_ip_from|real_ip_recursive|include)\b', original)):
        raise RuntimeError('Unexpected gateway access configuration')
    private_nginx = original.replace(b'server {',
        b'server {\n    if ($remote_addr != 127.0.0.1) { return 503; }', 1)
    nginx_path = u.WORK / 'nginx.private-gateway.conf'
    retained(u, nginx_path, private_nginx)
    mount['source'] = str(nginx_path)
    web['ports'] = []
    for name, (module, port, _) in API.items():
        service = config['services'][name]
        command = service.get('command')
        expected_ports = [{'target': 8000, 'published': port, 'host_ip': '127.0.0.1', 'protocol': 'tcp'}]
        if (not isinstance(command, list) or command[:4] != ['uvicorn', module, '--host', '0.0.0.0']
                or service.get('ports') != expected_ports or service.get('network_mode') == 'host'):
            raise RuntimeError('Unexpected API listener configuration: ' + name)
        command[3] = '127.0.0.1'
        service['ports'] = []
    target = u.WORK / 'compose.private-gateway.json'
    payload = (json.dumps(config, sort_keys=True, indent=2) + '\n').encode()
    retained(u, target, payload)
    return target


def verify_source(u, before):
    u.safe(NGINX_SOURCE)
    old = before['configs'].get(str(NGINX_SOURCE))
    if not old or snapshot.sha(NGINX_SOURCE.read_bytes()) != old:
        raise RuntimeError('Gateway configuration changed during private verification')
    return old


def normalize(u, after, before):
    source, private = NGINX_SOURCE, u.WORK / 'nginx.private-gateway.conf'
    old = verify_source(u, before)
    u.safe(private)
    if after['configs'].get(str(private)) != snapshot.sha(private.read_bytes()):
        raise RuntimeError('Gateway configuration changed during private verification')
    value = dict(after)
    value['configs'] = dict(after['configs'])
    value['configs'].pop(str(private))
    if str(source) in value['configs'] and value['configs'][str(source)] != old:
        raise RuntimeError('Gateway configuration identity is ambiguous')
    value['configs'][str(source)] = old
    return value
