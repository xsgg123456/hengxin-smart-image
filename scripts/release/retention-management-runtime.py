"""Pin installed source/image and preserve every existing Compose/native setting."""
import importlib.util
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('retry', Path(__file__).with_name('api-retry-deploy.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
m, r, gate = p.m, p.r, p.gate
n = m.module('retention-management-native')
SERVICES = r.SERVICES
limits = m.module('retirement-runtime').container_policy


def validate(work, release):
    assert re.fullmatch(r'domestic-retention-20261021-[0-9a-f]{7}', release)
    source = work / 'src'
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['frontendVersion'] == '0.2.46'
    assert manifest['migration'] == '0032' and manifest['overseasMigration'] == 'overseas_0019'
    assert 'backend/migrations/versions/0032_retention_observability.py' in manifest['files']
    assert len([name for name in manifest['files'] if name.startswith('backend/migrations/versions/0032_')]) == 1
    r.hashes(source, manifest)
    return source, manifest, 'hengxin-smart-image-backend:' + release


def baseline():
    assert r.sql('SELECT version_num FROM alembic_version') == '0031'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0019'
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == '0.2.45'


def topology():
    data = p.topology()
    data['nativeSnapshots'] = n.snapshots()
    data['containerLimits'] = {service: limits(m.live(m.container('domestic', service))) for service in SERVICES}
    return data


def same_settings(old, new):
    m.same_settings(old, new, [*SERVICES, 'migrate'])


def prepare(work, source, manifest, image):
    assert not (work / 'PREPARED').exists()
    identity = m.image_id(work, image)
    baseline()
    m.assets_safe(source)
    data = topology()
    old = json.loads(m.compose(data['domestic'], 'config', '--format', 'json', capture=True))
    m.check_live_config('domestic', old)
    overlay = {'services': {service: dict(image=identity, build={
        'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}) for service in (*SERVICES, 'migrate')}}
    m.private(work / 'domestic-overlay.json', overlay)
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json',
                              overlay=work / 'domestic-overlay.json', capture=True))
    same_settings(old, new)
    m.private(work / 'domestic-compose.private.json', old)
    m.private(work / 'topology.json', data)
    m.private(work / 'native-snapshots.private.json', data['nativeSnapshots'])
    n.prepare(work, source, manifest['release'], data['nativeSnapshots'])
    gate.save(work)
    assert topology() == data, 'Topology drift during prepare'
    m.private(work / 'PREPARED', identity)


def unchanged(data):
    # Do not require cleanup to be running before its final startup.
    for group in m.GROUPS:
        for name, identity in data[group]['ids'].items():
            live = m.live(name)
            if group != 'domestic' or name not in {m.container('domestic', s) for s in SERVICES}:
                assert live['Id'] == identity and live['Image'] == data['images'][group][name]
                assert live['State']['Running'], 'Unrelated service stopped'
            assert live['Mounts'] == data[group]['mounts'][name], 'Live mounts changed'
        assert all(m.digest(path) == value for path, value in data[group]['files'].items())
    for unit, row in data['nativeProcesses'].items():
        if unit in n.UNITS:
            continue
        pid = m.run('systemctl', 'show', unit, '-p', 'MainPID', '--value', capture=True)
        assert pid == row['pid'], 'Unrelated native PID changed'
        assert m.digest(Path('/proc') / pid / 'cmdline') == row['argv']
        assert m.digest(Path('/proc') / pid / 'environ') == row['environment']
    assert all(m.digest(path) == value for path, value in data['nativeFiles'].items()), 'Existing native files changed'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0019'


def installed(work, data, image):
    identity = m.image_id(work, image)
    for service in SERVICES:
        live = m.live(m.container('domestic', service))
        assert live['Image'] == identity and live['State']['Running']
        assert live['State'].get('Health', {}).get('Status', 'healthy') == 'healthy'
        assert limits(live) == data['containerLimits'][service], 'Container execution limits changed'
    config = json.loads(m.compose(data['domestic'], 'config', '--format', 'json',
        overlay=work / 'domestic-overlay.json', capture=True))
    same_settings(json.loads((work / 'domestic-compose.private.json').read_text()), config)
    m.check_live_config('domestic', config)
    assert r.sql('SELECT version_num FROM alembic_version') == '0032'
    m.run('docker', 'exec', m.container('domestic', 'api'), 'python', '-c',
          'from app.retention.state import HISTORY_AGE; assert HISTORY_AGE.total_seconds()==259200')
    unchanged(data)
