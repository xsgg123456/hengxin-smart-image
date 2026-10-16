"""One-shot recovery of the inspected 106d07d ExecStart statistics false alarm.

Run outside the immutable release source:
  python overseas-images-recover.py overseas-20261016-106d07d recover \
    --source /opt/hengxin-releases/overseas-20261016-106d07d/src
Only the old release dependency chain executes production operations. No deploy
replay, native restart, backup replacement, migration or database restore.
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

RELEASE = 'overseas-20261016-106d07d'
WORK = Path('/opt/hengxin-releases') / RELEASE


def normalize_exec_start(value):
    """Same narrow transformation as images-deploy; no sibling imports needed."""
    return re.sub(
        r'(\{ path=.*? ; argv\[\]=.*? ; ignore_errors=(?:yes|no))'
        r' ; start_time=[^;{}]* ; stop_time=[^;{}]* ; pid=\d+'
        r' ; code=[^;{}]* ; status=[^;{}]* \}', r'\1 }', value)


def normalize_native(value):
    result = copy.deepcopy(value)
    for state in result.values():
        state['fields']['ExecStart'] = normalize_exec_start(state['fields']['ExecStart'])
    return result


def load(source):
    path = source / 'scripts/release/overseas-images-deploy.py'
    spec = importlib.util.spec_from_file_location('original_images_release', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    original = value.d.domestic_native
    value.d.domestic_native = lambda: normalize_native(original())
    return value


def preflight(c, work, source, manifest, image):
    d, m = c.d, c.d.m
    assert manifest['release'] == RELEASE, 'Recovery is pinned to the inspected release'
    assert source == work / 'src', 'Original immutable source required'
    assert not (work / 'RECOVERY_STARTED').exists(), 'Do not replay recovery'
    assert (work / 'DEPLOY_STARTED').read_text() == RELEASE
    assert (work / 'PHASE').read_text() == 'verify-installed', 'Unexpected failed phase'
    failure = json.loads((work / 'FAILURE.json').read_text())
    assert failure['phase'] == 'verify-installed' and failure['errorType'] == 'AssertionError'
    assert not (work / 'INSTALLED_VERIFIED').exists() and not (work / 'verification.json').exists()
    backup = d.BACKUPS / RELEASE
    assert (backup / 'COMPLETE').is_file(), 'Verified original backup required'
    data = json.loads((work / 'topology.json').read_text())
    assert json.loads((backup / 'full-topology.json').read_text()) == data, 'Backup topology mismatch'
    assert (backup / 'overseas.dump').stat().st_size > 0, 'Original database backup missing'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Original drained backup required'
    for name, release in (('OVERSEAS_RELEASE.json', c.BASE_RELEASE),
                          ('FRONTEND_RELEASE.json', c.BASE_FRONTEND_RELEASE)):
        assert json.loads((m.APP / name).read_text())['release'] == release, 'Release baseline drift'
        assert (m.APP / name).read_bytes() == (backup / name).read_bytes(), 'Backup manifest mismatch'
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == d.BASE_VERSION
    for name in ('frontend/package.json', 'frontend/dist/index.html', 'frontend/dist/index.html.gz'):
        saved, current = backup / name, m.APP / name
        assert saved.exists() == current.exists(), 'Frontend entry presence changed'
        if saved.exists():
            assert saved.read_bytes() == current.read_bytes(), 'Frontend already changed'
    identity = m.image_id(work, image)  # Includes the original INSTALL_TEST_IMAGE_ID gate.
    assert (work / 'PREPARED').read_text() == (work / 'UPLOAD_CAPACITY_IMAGE_ID').read_text() == identity
    d.r.hashes(source, manifest)
    d.schemas()
    d.prepared_settings(work, data, identity, source)
    native = normalize_native(json.loads((work / 'domestic-native.json').read_text()))
    assert d.domestic_native() == native, 'Domestic native identity changed'
    target = Path((work / 'native-target').read_text())
    assert target == Path('/opt/hengxin-overseas-releases') / RELEASE / 'backend'
    d.r.hashes(target.parent, {'files': {n: h for n, h in manifest['files'].items() if n.startswith('backend/')}})
    for unit in d.u.UNITS:
        c.native_state(unit, target)
        pointer = c.SYSTEMD / (unit + '.service.d') / d.u.DROP
        assert pointer.read_text() == c.a.native_pointer(target, unit), 'Native candidate pointer drift'
        effective = m.run('systemctl', 'show', unit, '-p', 'DropInPaths', '--value', capture=True).split()
        assert str(pointer) in effective and all(Path(p).name <= d.u.DROP for p in effective)
        assert all(p.name <= d.u.DROP for p in pointer.parent.glob('*.conf'))
    actual = m.live(d.u.API)
    assert not actual['State']['Running'] and actual['Image'] == identity, 'Candidate API must be stopped'
    assert actual['HostConfig']['Memory'] == d.resources.API_MEMORY
    assert actual['Mounts'] == data['overseas']['mounts'][d.u.API]
    for group in m.GROUPS:
        baseline = data[group]
        for name, container_id in baseline['ids'].items():
            if name != d.u.API:
                current = m.live(name)
                assert current['Id'] == container_id and current['State']['Running']
                assert current['Mounts'] == baseline['mounts'][name]
        assert all(m.digest(p) == h for p, h in baseline['files'].items())
    pointers = {str(c.SYSTEMD / (unit + '.service.d') / d.u.DROP) for unit in d.u.UNITS}
    assert all(m.digest(p) == h for p, h in data['nativeFiles'].items() if p not in pointers)
    edge = (work / 'edge-before.conf').read_text()
    assert (backup / 'edge.conf').read_text() == edge
    assert m.EDGE.read_text() == d.closed_config(edge)
    for label, path in (('edge', m.EDGE), ('inner', d.proxy.inner(m))):
        before = (work / f'upload-{label}-before.conf').read_text()
        assert before == (work / f'upload-{label}-after.conf').read_text(), 'Image release must not change proxy settings'
        c.a.proxy_baseline(before)
        assert (edge if label == 'edge' else path.read_text()) == before
    d.closed()
    d.u.wait_worker_ready()
    d.wait_empty(work, 'recovery-preflight-idle')
    return data, native, target, backup, identity, edge


def recover(c, work, source, manifest, image):
    d, m, u, r, verify = c.d, c.d.m, c.d.u, c.d.r, c.d.verify
    data, native, target, backup, identity, edge = preflight(c, work, source, manifest, image)
    overlay = work / 'overseas-overlay.json'
    m.private(work / 'RECOVERY_STARTED', 'Inspected ExecStart statistics reset; immutable baseline normalized in memory')
    phase = 'restore-api'
    try:
        m.private(work / 'RECOVERY_PHASE', phase)
        m.compose(data['overseas'], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
                  '--wait', '--wait-timeout', '180', 'api', overlay=overlay)
        phase = 'verify-installed'
        m.private(work / 'RECOVERY_PHASE', phase)
        d.installed(work, manifest, identity, data, native, target)
        d.proxy.install_inner(work, backup, m)
        m.run('docker', 'exec', r.PREFIX + 'web-1', 'nginx', '-t')
        m.run('docker', 'exec', r.PREFIX + 'web-1', 'nginx', '-s', 'reload')
        verify.proxy()
        phase = 'publish-frontend'
        m.private(work / 'RECOVERY_PHASE', phase)
        m.assets_safe(source)
        r.publish(source)
        verify.frontend(source, manifest)
        d.closed()
        phase = 'open-and-verify'
        m.private(work / 'RECOVERY_PHASE', phase)
        m.EDGE.write_text((work / 'upload-edge-after.conf').read_text())
        u.reload_edge()
        verify.public()
        d.proxy.verify(work, m, verify)
        verify.frontend(source, manifest)
        d.resources_unchanged(data, native, {'native': target, 'overlay': overlay})
        for name in ('OVERSEAS_RELEASE.json', 'FRONTEND_RELEASE.json'):
            m.private(m.APP / name, manifest)
        m.private(work / 'verification.json', dict(release=manifest['release'], image=identity,
            migration=d.DOMESTIC_MIGRATION, overseasMigration=d.TARGET_MIGRATION, backup=str(backup),
            sourceHashes=True, domesticIdentityUnchanged=True, skillsVerified=True, businessDeletion=False,
            recovery='ExecStart statistics normalized; original source and backup retained'))
        m.private(work / 'RECOVERY_PHASE', 'complete')
        m.private(work / 'PHASE', 'complete')
        print('IMAGES_RECOVERY_COMPLETE ' + manifest['release'], flush=True)
    except BaseException as exc:
        try:
            d.close_edge(edge)
            d.closed()
            d.proxy.restore_inner(work, m)
        finally:
            try:
                m.compose(data['overseas'], 'stop', '-t', '30', 'api', overlay=overlay)
            finally:
                m.private(work / 'RECOVERY_FAILURE.json', dict(phase=phase, errorType=type(exc).__name__,
                    recovery='Keep intake closed; no recovery replay, DB restore or native stop'))
        raise


def main():
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    os.umask(0o077)
    assert os.geteuid() == 0, 'Production recovery requires root'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release', choices=[RELEASE])
    parser.add_argument('action', choices=['recover'])
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    assert args.source == WORK / 'src' and args.source.resolve() == args.source, 'Explicit original source required'
    c = load(args.source)
    source, manifest, image = c.validate(WORK, RELEASE)
    c.d.m.module('release-retention').managed(
        lambda: recover(c, WORK, source, manifest, image), argv=[sys.argv[0], RELEASE, 'recover'])


if __name__ == '__main__':
    main()
