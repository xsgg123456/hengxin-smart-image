"""Generate .245 HTTPS/proxy candidates only; never install units or start services."""
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess

ROOT = Path('/opt/hengxin-lan')
CERT = Path('/opt/1panel/www/sites/zhitu/ssl')
UNIT = 'hengxin-container-proxy.service'
NETWORKS = {f'network-{i}': subnet for i, subnet in enumerate((
    '172.19.0.0/16', '172.18.0.0/16', '172.30.245.0/24',
    '172.21.0.0/16', '172.22.0.0/16', '172.20.0.0/16'))}
NGINX = '''user nginx;
worker_processes auto;
pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 1024; }
http {
    access_log /dev/stdout;
    client_body_temp_path /tmp/client_temp;
    proxy_temp_path /tmp/proxy_temp;
    fastcgi_temp_path /tmp/fastcgi_temp;
    uwsgi_temp_path /tmp/uwsgi_temp;
    scgi_temp_path /tmp/scgi_temp;
    server {
        listen 192.168.1.245:443 ssl;
        server_name zhitu.qhhengxin.top;
        ssl_certificate /etc/nginx/tls/fullchain.pem;
        ssl_certificate_key /etc/nginx/tls/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        allow 192.168.1.0/24;
        allow 192.168.2.0/23;
        deny all;
        if ($host != zhitu.qhhengxin.top) { return 444; }
        # Outer limit includes multipart overhead; inner business limits remain.
        client_max_body_size 512m;
        client_body_timeout 300s;
        add_header X-Hengxin-Environment lan-245 always;
        location / {
            proxy_pass http://127.0.0.1:18080;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header X-Forwarded-Host $host;
            proxy_set_header X-Forwarded-Port 443;
            proxy_set_header Connection "";
            proxy_buffering off;
            proxy_request_buffering off;
            proxy_cache off;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }
    }
}
'''


def validate_networks(compose, inspected):
    if compose.get('name') != 'hengxin-lan' or set(compose['networks']) != set(NETWORKS):
        raise ValueError('unexpected compose project/networks')
    expected_names = {'hengxin-lan-' + key for key in NETWORKS}
    if len(inspected) != 6 or {n['Name'] for n in inspected} != expected_names:
        raise ValueError('unexpected network inventory')
    for network in inspected:
        key = network['Name'].removeprefix('hengxin-lan-')
        subnet = ipaddress.ip_network(NETWORKS[key])
        labels = network.get('Labels') or {}
        if (compose['networks'][key].get('name') != network['Name']
                or network.get('Driver') != 'bridge' or network.get('Scope') != 'local'
                or network.get('EnableIPv6') or labels.get('com.docker.compose.project') != 'hengxin-lan'
                or labels.get('com.docker.compose.network') != key
                or network['IPAM']['Config'] != [{'Subnet': str(subnet), 'Gateway': str(subnet[1])}]):
            raise ValueError('network CIDR/ownership drift')
    return sorted(NETWORKS.values())


def build(compose, inspected):
    cidrs = validate_networks(compose, inspected)
    web = compose['services']['domestic-web']
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', web['image']):
        raise ValueError('immutable nginx image required')
    if web.get('ports') != [{'target': 80, 'published': '18080', 'host_ip': '127.0.0.1', 'protocol': 'tcp'}]:
        raise ValueError('loopback web endpoint drift')
    volumes = [{'type': 'bind', 'source': str(source), 'target': target,
                'read_only': True, 'bind': {'create_host_path': False}}
               for source, target in ((ROOT / 'edge-nginx.conf', '/etc/nginx/nginx.conf'),
                                      (CERT / 'fullchain.pem', '/etc/nginx/tls/fullchain.pem'),
                                      (CERT / 'privkey.pem', '/etc/nginx/tls/privkey.pem'))]
    edge = {'name': 'hengxin-lan-edge', 'services': {'https': {
        'image': web['image'], 'pull_policy': 'never', 'container_name': 'hengxin-lan-https',
        'network_mode': 'host', 'restart': 'unless-stopped', 'entrypoint': ['nginx'],
        'command': ['-g', 'daemon off;'], 'read_only': True, 'volumes': volumes,
        'tmpfs': ['/tmp:rw,nosuid,nodev,size=64m'], 'security_opt': ['no-new-privileges:true'],
        'logging': {'driver': 'json-file', 'options': {'max-size': '10m', 'max-file': '3'}}}}}
    unit = '\n'.join([
        '[Unit]', 'Description=Hengxin container-only loopback proxy relay',
        'After=network-online.target docker.service mihomo.service',
        'Wants=network-online.target', 'Requires=docker.service mihomo.service',
        'StartLimitIntervalSec=0', '[Service]', 'Type=simple', 'User=nobody',
        'ExecStart=/usr/bin/socat TCP4-LISTEN:7891,bind=172.30.245.1,reuseaddr,fork TCP4:127.0.0.1:7890',
        '# Retry while Docker recreates its bridge during boot.',
        'Restart=always', 'RestartSec=5s', 'NoNewPrivileges=true', 'ProtectSystem=strict',
        'ProtectHome=true', 'PrivateTmp=true', 'PrivateDevices=true',
        'CapabilityBoundingSet=', 'RestrictAddressFamilies=AF_INET AF_UNIX',
        'IPAddressDeny=any', 'IPAddressAllow=127.0.0.0/8',
        *['IPAddressAllow=' + cidr for cidr in cidrs],
        '[Install]', 'WantedBy=multi-user.target', ''])
    return {'edge-compose.json': json.dumps(edge, indent=2) + '\n',
            'edge-nginx.conf': NGINX, UNIT: unit}


def protected(path, directory=False):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise ValueError('unsafe path')
    info = path.stat()
    if (info.st_uid != 0 or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))):
        raise ValueError('private root-owned path required')


def write_outputs(outputs):
    if set(outputs) != {'edge-compose.json', 'edge-nginx.conf', UNIT}:
        raise ValueError('unexpected output inventory')
    protected(ROOT, directory=True)
    # Refuse the whole batch before writing if any previous candidate is present.
    if any((ROOT / name).exists() or (ROOT / name).is_symlink() for name in outputs):
        raise FileExistsError('candidate already exists')
    for name, content in outputs.items():
        fd = os.open(ROOT / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())


def main():
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('target host/root required')
    protected(ROOT, directory=True)
    for path in (ROOT / 'compose.json', CERT / 'fullchain.pem', CERT / 'privkey.pem'):
        protected(path)
    if not os.access('/usr/bin/socat', os.X_OK):
        raise RuntimeError('socat required')
    addresses = json.loads(subprocess.check_output(['ip', '-j', '-4', 'addr', 'show']))
    if '192.168.1.245' not in {a['local'] for interface in addresses for a in interface['addr_info']}:
        raise RuntimeError('required LAN interface missing')
    compose = json.loads((ROOT / 'compose.json').read_text())
    inspected = json.loads(subprocess.check_output(
        ['docker', 'network', 'inspect', *['hengxin-lan-' + key for key in NETWORKS]]))
    outputs = build(compose, inspected)
    image = compose['services']['domestic-web']['image']
    found = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))
    if len(found) != 1 or found[0]['Id'] != image:
        raise RuntimeError('local immutable image missing')
    write_outputs(outputs)
    print('Generated protected HTTPS and proxy candidates only; no units installed or services started.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Edge preparation refused; inspect target identity, protected paths and network/image inventory privately.')
