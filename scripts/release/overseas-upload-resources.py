"""Exact overseas API capacity override; preserve every unrelated Compose setting."""
import copy

API_MEMORY = 3 * 1024 ** 3


def overlay(source, identity):
    return {'services': {'api': {'image': identity, 'mem_limit': API_MEMORY,
            'build': {'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}}}}


def same_settings(before, after, m):
    assert int(after['services']['api']['mem_limit']) == API_MEMORY, 'API memory limit drift'
    normalized = copy.deepcopy(after)
    normalized['services']['api'].pop('mem_limit')
    if 'mem_limit' in before['services']['api']:
        normalized['services']['api']['mem_limit'] = before['services']['api']['mem_limit']
    m.same_settings(before, normalized, ['api'])


def test_capacity(work, image, m):
    identity = m.image_id(work, image)
    m.run('docker', 'run', '--rm', '--init', '--memory', str(API_MEMORY),
          '--network', 'none', '--entrypoint', 'python', '-e', 'APP_ENV=test', identity,
          '-m', 'pytest', '-q', 'tests/test_overseas_upload_limits.py')
    m.private(work / 'UPLOAD_CAPACITY_IMAGE_ID', identity)
