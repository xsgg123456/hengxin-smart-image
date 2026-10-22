"""Update domestic API and native cleanup code; preserve all unrelated runtimes."""
import importlib.util
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('retry_helpers', Path(__file__).with_name('api-retry-deploy.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
m, r, gate = p.m, p.r, p.gate
n = m.module('domestic-record-filters-native')
limits = m.module('retirement-runtime').container_policy
CONSUMERS = ('api-image-worker', 'image-variants')
PRODUCERS = ('outbox', 'api-image-outbox')


def validate(work, release):
    assert re.fullmatch(r'domestic-record-filters-20261022-[0-9a-f]{7}', release)
    source = work / 'src'
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['frontendVersion'] == '0.2.49'
    assert manifest['migration'] == '0032' and manifest['overseasMigration'] == 'overseas_0020'
    assert 'backend/app/modules/api_image_edits/listing.py' in manifest['files']
    r.hashes(source, manifest)
    return source, manifest, 'hengxin-smart-image-backend:' + release


def schemas():
    assert r.sql('SELECT version_num FROM alembic_version') == '0032'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0020'


def baseline():
    schemas()
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == '0.2.48'


def topology():
    data = p.topology()
    data['nativeSnapshots'] = n.snapshots()
    data['nativeOverrides'] = n.override_state()
    data['containerLimits'] = {service: limits(m.live(m.container('domestic', service))) for service in r.SERVICES}
    return data


def same_settings(old, new):
    m.same_settings(old, new, ['api'])
    # Only image is overridden, even the previous build configuration is preserved.
    assert old['services']['api'].get('build') == new['services']['api'].get('build')


def prepare(work, source, manifest, image):
    assert not (work / 'PREPARED').exists()
    identity = m.image_id(work, image)
    baseline()
    m.assets_safe(source)
    data = topology()
    old = json.loads(m.compose(data['domestic'], 'config', '--format', 'json', capture=True))
    m.check_live_config('domestic', old)
    overlay = work / 'domestic-overlay.json'
    m.private(overlay, {'services': {'api': {'image': identity}}})
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json', overlay=overlay, capture=True))
    same_settings(old, new)
    m.private(work / 'domestic-compose.private.json', old)
    m.private(work / 'topology.json', data)
    gate.save(work)
    n.prepare(work, source, manifest['release'], data['nativeSnapshots'])
    assert topology() == data, 'Topology drift during prepare'
    m.private(work / 'PREPARED', identity)


def unchanged(data):
    for group in m.GROUPS:
        for name, identity in data[group]['ids'].items():
            live = m.live(name)
            assert live['State']['Running'], 'Unrelated service stopped'
            if name != m.container('domestic', 'api'):
                assert live['Id'] == identity and live['Image'] == data['images'][group][name]
            assert live['Mounts'] == data[group]['mounts'][name], 'Live mounts changed'
        # Domestic nginx is temporarily gated; validate its original file after reopening.
        for path, digest in data[group]['files'].items():
            assert m.digest(path) == digest, 'Compose configuration changed'
    assert all(m.digest(path) == value for path, value in data['nativeFiles'].items()
               if path not in n.overrides()), 'Native auth/policy files changed'
    for unit, row in data['nativeProcesses'].items():
        if unit in n.UNITS:
            continue
        pid = m.run('systemctl', 'show', unit, '-p', 'MainPID', '--value', capture=True)
        assert pid == row['pid'], 'Unrelated native PID changed'
        assert m.digest(Path('/proc') / pid / 'cmdline') == row['argv']
        assert m.digest(Path('/proc') / pid / 'environ') == row['environment']
    schemas()


def installed(work, data, image):
    api = m.live(m.container('domestic', 'api'))
    assert api['Image'] == m.image_id(work, image) and api['State']['Running']
    assert api['State'].get('Health', {}).get('Status', 'healthy') == 'healthy'
    for service in r.SERVICES:
        assert limits(m.live(m.container('domestic', service))) == data['containerLimits'][service]
    old = json.loads((work / 'domestic-compose.private.json').read_text())
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json',
        overlay=work / 'domestic-overlay.json', capture=True))
    same_settings(old, new)
    m.check_live_config('domestic', new)
    unchanged(data)
    n.verify(work)


def start_existing(data, services):
    for service in services:
        name = m.container('domestic', service)
        live = m.live(name)
        assert live['Id'] == data['domestic']['ids'][name]
        assert live['Image'] == data['images']['domestic'][name]
        m.run('docker', 'start', name)
