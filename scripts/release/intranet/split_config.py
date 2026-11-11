"""Add static services and gateway routes without replacing business services."""
import copy
import json
import os
from pathlib import Path

import scopes
import snapshot


def ui_config(scope):
    scopes.validate(scope)
    return (f'server {{\n listen 80;\n root /usr/share/nginx/html;\n index index.html;\n'
            f' location ~ ^/(?:{scope}/)?assets/(?<asset>.+)$ {{\n'
            ' try_files /assets/$asset @previous_assets;\n }\n'
            ' location @previous_assets {\n root /usr/share/nginx/previous;\n'
            ' try_files /assets/$asset =404;\n }\n'
            f' location / {{\n rewrite ^/{scope}/(.*)$ /$1 break;\n'
            ' try_files $uri $uri/ /index.html;\n }\n}\n').encode()


def gateway(original):
    text = original.decode()
    old = '    location / {\n        try_files $uri $uri/ /index.html;\n    }'
    if text.count(old) != 1 or 'resolver ' in text or '-ui' in text:
        raise RuntimeError('Unexpected existing gateway configuration')
    # Resolve recreated application containers dynamically instead of caching
    # their old IP until an unrelated gateway restart.
    text = text.replace('    index index.html;', '    index index.html;\n    resolver 127.0.0.11 valid=5s ipv6=off;')
    for name in ('domestic-api', 'overseas-api', 'identity-api'):
        text = text.replace('proxy_pass http://' + name + ':8000;',
                            'set $upstream http://' + name + ':8000;\n        proxy_pass $upstream;')
    blocks = ['    location ^~ /assets/ { try_files $uri =404; }']
    for scope in scopes.GROUPS:
        blocks += [f'    location = /{scope} {{ return 302 /{scope}/$is_args$args; }}',
                   f'    location ^~ /{scope}/ {{ set $ui http://{scope}-ui:80; proxy_pass $ui; }}']
    blocks.append('    location / { set $ui http://shared-ui:80; proxy_pass $ui; }')
    return text.replace(old, '\n'.join(blocks)).encode()


def compose(u, original, releases):
    value = copy.deepcopy(original)
    expected = set(u.APPS) | u.DATA
    if value.get('name') != 'hengxin-lan' or set(value['services']) != expected:
        raise RuntimeError('Expected the verified legacy compose before migration')
    web = original['services']['domestic-web']
    prior = [v for v in web['volumes'] if v.get('target') == '/usr/share/nginx/html']
    if len(prior) != 1 or not prior[0].get('read_only'):
        raise RuntimeError('Unexpected legacy frontend mount')
    for scope in scopes.GROUPS:
        root = snapshot.release_path(releases[scope])
        service = copy.deepcopy(web)
        service['container_name'] = 'hengxin-lan-' + scopes.UI[scope]
        service.pop('ports', None)
        service['networks'] = {n: {'aliases': [scopes.UI[scope]]} for n in web['networks']}
        service['volumes'] = [
            {'type': 'bind', 'source': str(u.ROOT/(scope+'-ui.conf')),
             'target': '/etc/nginx/conf.d/default.conf', 'read_only': True,
             'bind': {'create_host_path': False}},
            {'type': 'bind', 'source': str(root/'frontend'),
             'target': '/usr/share/nginx/html', 'read_only': True,
             'bind': {'create_host_path': False}},
            {'type': 'bind', 'source': prior[0]['source'],
             'target': '/usr/share/nginx/previous', 'read_only': True,
             'bind': {'create_host_path': False}},
        ]
        value['services'][scopes.UI[scope]] = service
    if any(value['services'][n] != original['services'][n] for n in expected):
        raise RuntimeError('Migration attempted to alter an existing service')
    return value


def bound_write(u, path, content, expected):
    """Preserve the inode already bind-mounted into the running gateway."""
    path = Path(path)
    u.safe(path)
    if snapshot.sha(path.read_bytes()) != expected:
        raise RuntimeError('Concurrent gateway configuration change')
    fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
    try:
        opened, actual = os.fstat(fd), path.stat()
        if (opened.st_dev, opened.st_ino) != (actual.st_dev, actual.st_ino):
            raise RuntimeError('Gateway configuration identity changed')
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(content)
            stream.truncate()
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def check_gateway(u, config, original):
    # Read-only ephemeral nginx config check: no ports, no business commands.
    network = next(iter(original['services']['domestic-web']['networks']))
    network = original['networks'][network]['name']
    image = original['services']['domestic-web']['image']
    u.run(['docker', 'run', '--rm', '--network', network, '--pull', 'never',
           '--mount', 'type=bind,src='+str(config)+',dst=/etc/nginx/conf.d/default.conf,readonly',
           image, 'nginx', '-t'], timeout=60)


def reload_gateway(u):
    u.run(['docker', 'exec', 'hengxin-lan-domestic-web', 'nginx', '-t'])
    u.run(['docker', 'exec', 'hengxin-lan-domestic-web', 'nginx', '-s', 'reload'])
