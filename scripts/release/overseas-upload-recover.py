"""One-shot forward recovery of the inspected 0.2.33 native drop-in precedence failure."""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

NEW_DROP = '99-overseas-upload.conf'


def load(work):
    path = work / 'src/scripts/release/overseas-upload-deploy.py'
    spec = importlib.util.spec_from_file_location('upload_deploy', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def pointers(d, work, data, target, backup):
    old = d.u.DROP
    expected = {}
    for unit in d.u.UNITS:
        folder = Path('/etc/systemd/system') / (unit + '.service.d')
        path = folder / old
        saved = backup / folder.name / old
        assert d.m.digest(saved) == data['nativeFiles'][str(path)], 'Saved pointer mismatch'
        assert not (folder / NEW_DROP).exists(), 'Recovery pointer already exists'
        assert all(p.name < NEW_DROP for p in folder.glob('*.conf')), 'Higher priority override exists'
        command = (str(target / '.venv/bin/celery') + ' -A app.overseas.execution.worker:celery_app worker '
                   '--pool=prefork --concurrency=5 --queues=overseas.cli --loglevel=INFO --hostname=overseas@%H'
                   if unit.endswith('worker') else str(target / '.venv/bin/python') + ' -m app.overseas.execution.outbox')
        assert path.read_text() == '[Service]\nWorkingDirectory=' + str(target) + '\nExecStart=\nExecStart=' + command + '\n'
        expected[str(path)] = saved
    for path, digest in data['nativeFiles'].items():
        if path not in expected:
            assert d.m.digest(path) == digest, 'Unrelated native configuration drift'
    return expected


def recover(d, work, source, manifest, image):
    m, u, r, verify = d.m, d.u, d.r, d.verify
    assert not (work / 'RECOVERY_STARTED').exists(), 'Do not replay recovery'
    assert (work / 'PHASE').read_text() == 'verify-installed'
    failure = json.loads((work / 'FAILURE.json').read_text())
    assert failure['phase'] == 'verify-installed' and failure['errorType'] == 'AssertionError'
    assert not (work / 'INSTALLED_VERIFIED').exists() and not (work / 'verification.json').exists()
    backup = d.BACKUPS / manifest['release']
    assert (backup / 'COMPLETE').exists()
    identity = m.image_id(work, image)
    assert (work / 'PREPARED').read_text() == (work / 'UPLOAD_CAPACITY_IMAGE_ID').read_text() == identity
    data = json.loads((work / 'topology.json').read_text())
    native = json.loads((work / 'domestic-native.json').read_text())
    target = Path((work / 'native-target').read_text())
    overlay = work / 'overseas-overlay.json'
    d.schemas()
    d.prepared_settings(work, data, identity, source)
    assert d.domestic_native() == native
    actual = m.live(u.API)
    assert not actual['State']['Running'] and actual['Image'] == identity
    assert actual['HostConfig']['Memory'] == d.resources.API_MEMORY
    assert actual['Mounts'] == data['overseas']['mounts'][u.API]
    for group in m.GROUPS:
        baseline = data[group]
        for name, container_id in baseline['ids'].items():
            if name != u.API:
                current = m.live(name)
                assert current['Id'] == container_id and current['State']['Running']
                assert current['Mounts'] == baseline['mounts'][name]
        assert all(m.digest(p) == h for p, h in baseline['files'].items())
    saved_pointers = pointers(d, work, data, target, backup)
    r.hashes(target.parent, {'files': {n: h for n, h in manifest['files'].items() if n.startswith('backend/')}})
    edge = (work / 'edge-before.conf').read_text()
    assert m.EDGE.read_text() == d.closed_config(edge)
    assert d.proxy.inner(m).read_text() == (work / 'upload-inner-before.conf').read_text()
    d.closed()
    m.private(work / 'RECOVERY_STARTED', 'Inspected priority conflict; forward only, no DB restore')
    old_drop = u.DROP
    try:
        d.drain_and_stop(work)
        # Restore only the exact ineffective pointer this release wrote; preserve the 95 override.
        assert pointers(d, work, data, target, backup) == saved_pointers
        for path, saved in saved_pointers.items():
            m.private(Path(path), saved.read_text())
        u.DROP = NEW_DROP
        u.switch_native(target)
        m.compose(data['overseas'], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
                  '--wait', '--wait-timeout', '180', 'api', overlay=overlay)
        m.run('systemctl', 'start', *u.UNITS)
        d.installed(work, manifest, identity, data, native, target)
        d.proxy.install_inner(work, backup, m)
        m.run('docker', 'exec', r.PREFIX + 'web-1', 'nginx', '-t')
        m.run('docker', 'exec', r.PREFIX + 'web-1', 'nginx', '-s', 'reload')
        verify.proxy()
        m.assets_safe(source)
        r.publish(source)
        verify.frontend(source, manifest)
        d.closed()
        m.EDGE.write_text((work / 'upload-edge-after.conf').read_text())
        u.reload_edge()
        verify.public()
        d.proxy.verify(work, m, verify)
        verify.frontend(source, manifest)
        d.resources_unchanged(data, native, {'native': target, 'overlay': overlay})
        for name in ('OVERSEAS_RELEASE.json', 'FRONTEND_RELEASE.json'):
            m.private(m.APP / name, manifest)
        m.private(work / 'verification.json', dict(release=manifest['release'], image=identity,
            frontendVersion='0.2.33', migration='0028', overseasMigration='overseas_0015',
            sourceHashes=True, domesticIdentityUnchanged=True, skillsVerified=True,
            apiMemoryBytes=d.resources.API_MEMORY, recoveryPointer=NEW_DROP, backup=str(backup)))
        m.private(work / 'PHASE', 'complete')
        print('UPLOAD_RECOVERY_COMPLETE ' + manifest['release'], flush=True)
    except BaseException:
        try:
            d.close_edge(edge)
            d.closed()
            d.proxy.restore_inner(work, m)
        finally:
            m.compose(data['overseas'], 'stop', '-t', '30', 'api', overlay=overlay)
        raise
    finally:
        u.DROP = old_drop


def main():
    os.umask(0o077)
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    assert os.geteuid() == 0
    release, action = sys.argv[1:]
    assert re.fullmatch(r'overseas-20261014-00720c0', release) and action == 'recover'
    work = Path('/opt/hengxin-releases') / release
    d = load(work)
    source, manifest, image = d.validate(work, release)
    recover(d, work, source, manifest, image)


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    work = Path('/opt/hengxin-releases/overseas-20261014-00720c0')
    load(work).m.module('release-retention').managed(main)
