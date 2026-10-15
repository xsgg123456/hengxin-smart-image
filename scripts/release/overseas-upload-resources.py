"""Exact overseas API capacity override; preserve every unrelated Compose setting."""
import copy
from pathlib import Path

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


def unchanged(data, native, target, m, u, domestic_native):
    current = m.topology()
    for group in ('domestic', 'identity'):
        assert current[group] == data[group], 'Unrelated topology changed: ' + group
    before, after = data['overseas'], current['overseas']
    assert set(before['ids']) == set(after['ids']), 'Overseas resource set changed'
    assert before['mounts'] == after['mounts'], 'Overseas mount drift'
    assert all(after['ids'][name] == identity for name, identity in before['ids'].items() if name != u.API)
    assert all(m.digest(path) == digest for path, digest in before['files'].items()), 'Existing Compose configuration changed'
    assert all(after[key] == before[key] for key in ('project', 'cwd', 'env'))
    assert after['paths'] == [*before['paths'], str(target['overlay'])]
    assert domestic_native() == native, 'Domestic native process changed'
    assert current['native'] == {**data['native'], **{unit: str(target['native']) for unit in u.UNITS}}
    pointers = {str(Path('/etc/systemd/system') / (unit + '.service.d') / u.DROP) for unit in u.UNITS}
    assert {p: h for p, h in current['nativeFiles'].items() if p not in pointers} == {
        p: h for p, h in data['nativeFiles'].items() if p not in pointers}, 'Native config/environment drift'
