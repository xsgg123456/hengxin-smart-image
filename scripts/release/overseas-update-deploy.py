"""Forward-only overseas 0013 cutover; failure keeps overseas closed, never downgrades data.

Run build, prepare, deploy in order. A failed deploy requires operator inspection.
After 0013, do not restart the old API/worker against independent archives
or pending deletions. Recovery is a reviewed forward fix; restoring the dump requires
separate authorization and proof no post-backup business writes will be discarded.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location('overseas_update_runtime', Path(__file__).with_name('overseas-update-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
skills = r.module('overseas-skills-runtime')


def validate(work, release):
    source = work / 'src'
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['frontendVersion'] == '0.2.28'
    assert manifest['overseasMigration'] == 'overseas_0013' and manifest['migration'] == '0027'
    r.r.hashes(source, manifest)
    return source, manifest, 'hengxin-smart-image-backend:' + release


def untouched():
    names = ['hengxin-vps-staging-' + n + '-1' for n in ('api', 'outbox', 'api-image-worker', 'api-image-outbox', 'image-variants')]
    names += ['hengxin-identity-identity-api-1']
    return {name: r.run('docker', 'inspect', '--format', '{{.Id}}', name, capture=True) for name in names}


def prepare(work, source, manifest, image):
    identity = r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', image, capture=True)
    assert (work / 'INSTALL_TEST_IMAGE_ID').read_text() == identity
    assert r.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0012'
    assert json.loads((r.APP / 'frontend/package.json').read_text())['version'] == '0.2.27'
    assert not (work / 'PREPARED').exists()
    # Refuse overwriting shared unhashed assets used by the previous frontend.
    for file in (source / 'frontend/dist').rglob('*'):
        if file.is_file() and file.name not in ('index.html', 'index.html.gz'):
            dest = r.APP / 'frontend/dist' / file.relative_to(source / 'frontend/dist')
            assert not dest.exists() or dest.read_bytes() == file.read_bytes(), str(dest)
    r.roles_migratable()
    data = r.topology()
    r.private(work / 'old-topology.json', data)
    r.private(work / 'untouched.json', untouched())
    r.private(work / 'update-overlay.json', {'services': {name: {'image': identity,
        'pull_policy': 'never', 'volumes': [skills.overlay()]} for name in ('api', 'migrate')}})
    r.compose(data, 'config', '--quiet', overlay=work / 'update-overlay.json')
    target = r.prepare_native(source, manifest['release'])
    skills.preflight(r, work, target)
    r.private(work / 'native-target', str(target))
    r.private(work / 'PREPARED', identity)


def public_verify(source):
    for path in ('/api/overseas/v1/health/ready', '/api/v1/health/ready', '/api/identity/v1/config'):
        r.run('curl', '--retry', '10', '--retry-delay', '2', '--retry-connrefused', '-fsS', '-o', '/dev/null', r.r.ORIGIN + path)
    result = r.run('curl', '--retry', '10', '--retry-delay', '2', '--retry-connrefused', '-fsS', '-H', 'Accept-Encoding: identity', r.r.ORIGIN + '/', capture=True)
    assert result.strip() == (source / 'frontend/dist/index.html').read_text().strip(), 'Public index mismatch'
    for route in ('auth/me', 'tasks'):
        status = r.run('curl', '-sS', '-o', '/dev/null', '-w', '%{http_code}', r.r.ORIGIN + '/api/overseas/v1/' + route, capture=True)
        assert status in ('401', '403')


def deploy(work, source, manifest, image):
    identity = r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', image, capture=True)
    assert (work / 'PREPARED').read_text() == (work / 'INSTALL_TEST_IMAGE_ID').read_text() == identity
    assert r.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0012'
    data = json.loads((work / 'old-topology.json').read_text())
    assert r.topology() == data and untouched() == json.loads((work / 'untouched.json').read_text())
    r.roles_migratable()
    backup = Path('/opt/hengxin-backups') / manifest['release']
    assert not backup.exists()
    edge = r.EDGE.read_bytes()
    r.private(work / 'edge-before.conf', edge.decode())
    overlay = work / 'update-overlay.json'
    try:
        r.close_edge()
        # Stop only overseas API; worker/outbox continue draining already admitted jobs.
        r.compose(data, 'stop', '-t', '30', 'api')
        r.drain()
        r.run('systemctl', 'stop', r.UNITS[1])
        assert r.pending() == 0 and r.worker_idle()
        r.run('systemctl', 'stop', r.UNITS[0])
        assert r.pending() == 0
        r.backup(work, backup, data)
        target = Path((work / 'native-target').read_text())
        skills.install(r, work, target, backup)
        r.private(backup / 'edge.conf', edge.decode())
        # Mark before invoking migration: even a partially successful migration forbids old code.
        r.private(work / 'MIGRATION_STARTED', 'Forward-only; never auto-restore old business runtime')
        r.compose(data, 'run', '--rm', '--no-deps', 'migrate', overlay=overlay)
        assert r.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0013'
        r.switch_native(Path((work / 'native-target').read_text()))
        r.compose(data, 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '180', 'api', overlay=overlay)
        r.run('systemctl', 'start', *r.UNITS)
        # Resolve the replaced API address without restarting the shared domestic web container.
        r.run('docker', 'exec', r.r.PREFIX + 'web-1', 'nginx', '-t')
        r.run('docker', 'exec', r.r.PREFIX + 'web-1', 'nginx', '-s', 'reload')
        r.r.publish(source)
        r.verify(source, manifest, identity)
        skills.verify(r, work, target)
        assert untouched() == json.loads((work / 'untouched.json').read_text())
        # Validate the proxy route before restoring public overseas intake.
        r.run('curl', '--retry', '10', '--retry-delay', '2', '--retry-connrefused', '-fsS', '-H', 'Host: zhitu.qhhengxin.top', '-o', '/dev/null', 'http://127.0.0.1:18080/api/overseas/v1/health/ready')
        r.EDGE.write_bytes(edge)
        r.reload_edge()
        public_verify(source)
        r.private(r.APP / 'OVERSEAS_RELEASE.json', manifest)
        r.private(r.APP / 'FRONTEND_RELEASE.json', manifest)
        r.private(work / 'verification.json', {'release': manifest['release'], 'image': identity,
                  'migration': 'overseas_0013', 'domesticIdentityUnchanged': True, 'backup': str(backup)})
        print('OVERSEAS_UPDATE_COMPLETE ' + manifest['release'], flush=True)
    except BaseException:
        # Never stop an executor here: drain failure can mean a paid subprocess is alive.
        try:
            r.close_edge()
        finally:
            r.compose(data, 'stop', '-t', '30', 'api', overlay=overlay)
        print('OVERSEAS_INTAKE_CLOSED_FORWARD_RECOVERY_REQUIRED', flush=True)
        raise


def main():
    os.umask(0o077)
    release, action = sys.argv[1:3]
    assert re.fullmatch(r'overseas-20261013-[0-9a-f]{7}', release)
    work = Path('/opt/hengxin-releases') / release
    source, manifest, image = validate(work, release)
    if action == 'build':
        r.module('overseas-deploy').build(work, source, image)
    elif action == 'prepare':
        prepare(work, source, manifest, image)
    elif action == 'deploy':
        deploy(work, source, manifest, image)
    else:
        raise ValueError('Unknown update action')


if __name__ == '__main__':
    spec = importlib.util.spec_from_file_location('release_retention', Path(__file__).with_name('release-retention.py'))
    retention = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(retention)
    retention.managed(main)
