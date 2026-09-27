"""Validate the opt-in production composition without using .env or starting it."""
import json
import os
from pathlib import Path
import subprocess

from media_stack import ROOT


def resolved_services(directory, extra=(), all_profiles=False):
    empty = Path(directory) / 'empty.env'
    empty.write_text('', encoding='utf-8')
    infra = ROOT / 'hengxin-smart-image/infra'
    env = {key: value for key, value in os.environ.items()
           if key.upper() in ('PATH', 'SYSTEMROOT', 'TEMP', 'TMP', 'USERPROFILE', 'HOME', 'APPDATA', 'LOCALAPPDATA',
                              'PROGRAMDATA', 'PROGRAMFILES', 'PROGRAMFILES(X86)', 'COMSPEC', 'PATHEXT', 'WINDIR', 'SYSTEMDRIVE')
           or key.startswith('DOCKER_')}
    env.update(POSTGRES_PASSWORD='local-config-check-only', MINIO_ACCESS_KEY='local-config-check',
               MINIO_SECRET_KEY='local-config-check-only', APP_ENV='test', API_IMAGE_ENABLED='true')
    command = ['docker', 'compose', '--env-file', str(empty)]
    if all_profiles:
        command += ['--profile', '*']  # Inspection only; never starts services.
    for file in ('compose.yaml', 'compose.vps.yaml', 'compose.api-image.yaml', 'compose.media.yaml', *extra):
        command += ['-f', str(infra / file)]
    command += ['config', '--format', 'json']
    result = subprocess.run(command, env=env, capture_output=True, text=True, encoding='utf-8', timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)['services']


def check_composition(directory):
    services = resolved_services(directory)
    media, api, web = services['media-api'], services['api'], services['web']
    assert not media.get('ports'), 'media API must never publish a host port'
    assert media['environment']['MEDIA_INTERNAL_DELIVERY_ENABLED'] == 'true'
    assert api['environment']['MEDIA_INTERNAL_DELIVERY_ENABLED'] == 'false'
    assert media['environment']['DB_POOL_SIZE'] == '4'
    assert api['environment']['DB_POOL_SIZE'] == '5'
    assert all(x['environment']['DB_MAX_OVERFLOW'] == '0' for x in (media, api))
    assert int(media['mem_limit']) == 3 * 1024**3 and int(media['memswap_limit']) == int(media['mem_limit'])
    assert media['tmpfs'] == ['/tmp:size=1280m,mode=1777']
    assert next(x['source'] for x in web['volumes'] if x['target'] == '/etc/nginx/conf.d/default.conf').endswith('nginx.media.conf')
    assert 'media-api' in web['depends_on']
    assert '--concurrency=5' in services['api-image-worker']['command'], 'generation concurrency changed'
