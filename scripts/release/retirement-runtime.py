"""Prepare domestic retirement against the real 0029/0.2.39 production baseline."""
import importlib.util
import json
import os
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('member_runtime', Path(__file__).with_name('member-release-runtime.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
r = m.r
n = m.module('retirement-native')
LIMITS = ('Memory', 'MemoryReservation', 'MemorySwap', 'NanoCpus', 'CpuPeriod', 'CpuQuota',
          'CpusetCpus', 'PidsLimit', 'Ulimits', 'ReadonlyRootfs', 'CapAdd', 'CapDrop', 'SecurityOpt')


def container_policy(live):
    return {key: live['HostConfig'].get(key) for key in LIMITS}


def other_native(unit):
    pid, cwd = n.show(unit, 'MainPID'), n.show(unit, 'WorkingDirectory')
    assert int(pid) > 0 and os.readlink('/proc/' + pid + '/cwd') == cwd
    return dict(pid=pid, cwd=cwd)


def validate(work, release):
    assert re.fullmatch(r'domestic-retire-20261016-[0-9a-f]{7}', release)
    source = work / 'src'
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['frontendVersion'] == '0.2.40'
    assert manifest['migration'] == '0030' and manifest['overseasMigration'] == 'overseas_0017'
    r.hashes(source, manifest)
    return source, manifest, 'hengxin-smart-image-backend:' + release


def topology():
    data = m.topology()
    data['nativeProcesses'] = n.all_snapshots()
    for row in data['nativeProcesses'].values():
        data['nativeFiles'].update(row['files'])
    # Actual image IDs detect mutable tags; saved native snapshots detect daemon/PID drift.
    data['images'] = {group: {name: m.live(name)['Image'] for name in data[group]['ids']}
                      for group in m.GROUPS}
    data['containerLimits'] = {service: container_policy(m.live(m.container('domestic', service)))
                               for service in r.SERVICES}
    data['otherNative'] = {unit: other_native(unit)
                           for unit in m.UNITS if unit != n.UNIT}
    return data


def baseline():
    assert r.sql('SELECT version_num FROM alembic_version') == '0029'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0017'
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == '0.2.39'


def unchanged_other_groups(data):
    for group in ('identity', 'overseas'):
        for name, identity in data[group]['ids'].items():
            live = m.live(name)
            assert live['Id'] == identity and live['State']['Running']
            assert live['Image'] == data['images'][group][name]
    for unit, row in data['otherNative'].items():
        assert other_native(unit) == row
        m.run('systemctl', 'is-active', unit, capture=True)
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0017'


def prepare(work, source, manifest, image):
    assert not (work / 'PREPARED').exists()
    identity = m.image_id(work, image)
    baseline()
    m.assets_safe(source)
    data = topology()
    old = json.loads(m.compose(data['domestic'], 'config', '--format', 'json', capture=True))
    m.check_live_config('domestic', old)
    assert str(old['services']['api']['environment'].get('CLI_RETENTION_ENABLED')).lower() == 'true'
    names = [*r.SERVICES, 'migrate']
    overlay = work / 'domestic-overlay.json'
    m.private(overlay, {'services': {name: {'image': identity, 'build': {
        'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}} for name in names}})
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json', overlay=overlay, capture=True))
    m.same_settings(old, new, names)
    m.private(work / 'domestic-compose.private.json', old)
    m.private(work / 'topology.json', data)
    m.private(work / 'native-snapshots.private.json', data['nativeProcesses'])
    n.prepare(work, source, manifest['release'], data['nativeProcesses'])
    m.module('domestic-gate').save(work)
    m.module('retirement-backup').contract(source)
    assert topology() == data, 'Topology/process/config drift during prepare'
    m.private(work / 'PREPARED', identity)
