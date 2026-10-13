"""Reviewed first overseas release: build, prepare, then drained domestic cutover."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import importlib.util

spec = importlib.util.spec_from_file_location('runtime', Path(__file__).with_name('overseas-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
s = r.module('overseas-services')


def validate(work, release):
    source = work / 'src'
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['frontendVersion'] == '0.2.22'
    r.hashes(source, manifest)
    return source, manifest, 'hengxin-smart-image-backend:' + release


def build(work, source, image):
    r.run('docker', 'build', '-t', image, '-f', str(source / 'infra/Dockerfile.backend'), str(source))
    identity = r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', image, capture=True)
    ignored = ('test_local_codex', 'test_local_codex_control', 'test_local_codex_ports', 'test_phase11a_checks', 'test_phase11a_environment', 'test_phase11a_supervisor')
    args = ['-m', 'pytest', '-q', *('--ignore=tests/' + n + '.py' for n in ignored),
            '--deselect=tests/test_contracts.py::test_top_level_fields_match_frontend_interfaces']
    with (work / 'installation-tests.log').open('w') as log:
        subprocess.run(['docker', 'run', '--rm', '--init', '--network', 'none', '--entrypoint', 'python',
                        '-e', 'APP_ENV=test', identity, *args], stdout=log, stderr=subprocess.STDOUT, check=True)
    r.private(work / 'INSTALL_TEST_IMAGE_ID', identity)
    print('INSTALLATION_TESTS_PASS', flush=True)


def prepare(work, source, image, release):
    assert (work / 'INSTALL_TEST_IMAGE_ID').read_text() == r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', image, capture=True)
    assert r.sql('SELECT version_num FROM alembic_version') == '0026'
    assert not (work / 'PREPARED').exists()
    paths = r.inspect('api')['Config']['Labels']['com.docker.compose.project.config_files'].split(',')
    assert all(Path(p).is_file() and p.startswith('/opt/') for p in paths)
    r.private(work / 'old-paths.json', paths)
    data, native = s.setup(r, work, source, image)
    overlay = json.loads(Path(data['domestic_overlay']).read_text())
    web = json.loads(Path(data['web_overlay']).read_text())
    overlay.setdefault('networks', {}).update(web.get('networks', {}))
    overlay['services'].update(web['services'])
    for name in (*r.SERVICES, 'migrate'):
        overlay['services'].setdefault(name, {}).update(image=image, build={'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'})
    r.private(work / 'api-override.yaml', overlay)
    r.compose([*paths, work / 'api-override.yaml'], 'config', '--quiet')
    s.start_resources(r, data)
    s.install_executor(r, work, source, native)
    s.admin_candidate(r, work)
    target = r.prepare_native(source, release)
    r.private(work / 'native-target', str(target))
    r.private(work / 'PREPARED', 'isolated resources ready')


def deploy(work, source, manifest):
    assert (work / 'PREPARED').exists()
    assert (work / 'INSTALL_TEST_IMAGE_ID').read_text() == r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', 'hengxin-smart-image-backend:' + manifest['release'], capture=True)
    paths = json.loads((work / 'old-paths.json').read_text())
    new = [*paths, work / 'api-override.yaml']
    backup_dir = Path('/opt/hengxin-backups') / manifest['release']
    helper = source / 'scripts/release/image-inputs-worker.py'
    assert r.pending() == 0, 'In-flight work: defer cutover'
    assert r.sql('SELECT paused FROM api_image_channel WHERE id=1') == 'f'
    assert not backup_dir.exists()
    closed = drained = switched = opening = False
    try:
        closed = True
        r.compose(paths, 'stop', '-t', '30', 'web', 'api', 'outbox', 'api-image-outbox')
        r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
        r.worker(helper, 'api-drain')
        assert r.pending() == 0
        r.compose(paths, 'stop', '-t', '30', 'api-image-worker')
        r.worker(helper, 'native-stop')
        assert r.pending() == 0
        drained = True
        r.compose(paths, 'stop', '-t', '30', 'image-variants')
        r.backup(work, backup_dir, paths)
        r.compose(new, 'run', '--rm', '--no-deps', 'migrate')
        assert r.sql('SELECT version_num FROM alembic_version') == '0027'
        switched = True
        r.switch_native(Path((work / 'native-target').read_text()))
        r.run('systemctl', 'start', 'hengxin-vps-codex-worker')
        r.worker(helper, 'native-verify')
        r.compose(new, 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '180', *r.SERVICES)
        r.worker(helper, 'api-verify')
        r.ready()
        before = json.loads((backup_dir / 'baseline.json').read_text())
        after = r.baseline()
        assert {k:v for k,v in before.items() if k != 'schema'} == {k:v for k,v in after.items() if k != 'schema'}
        proxy = r.proxy_config()
        (r.APP / 'infra/nginx.vps.conf').write_text(proxy)
        r.publish(source)
        r.run('python3', str(source / 'scripts/release/overseas-verify.py'), manifest['release'], '--installed-only')
        r.install_edge()
        opening = True  # Web reopening can admit legacy CLI requests even while API-image is paused.
        r.compose(new, 'up', '-d', '--no-deps', '--wait', 'web')
        r.run('docker', 'exec', r.PREFIX + 'web-1', 'nginx', '-t')
        r.run('docker', 'exec', r.PREFIX + 'web-1', 'nginx', '-s', 'reload')
        # All installed/public checks precede opening the domestic generation channel.
        r.run('python3', str(source / 'scripts/release/overseas-verify.py'), manifest['release'])
        r.sql('UPDATE api_image_channel SET paused=false WHERE id=1')
        r.private(r.APP / 'OVERSEAS_RELEASE.json', manifest)
        r.private(r.APP / 'FRONTEND_RELEASE.json', manifest)
        print('DEPLOY_COMPLETE ' + manifest['release'], flush=True)
    except BaseException:
        if not closed:
            raise
        if not drained or opening:
            r.compose(new if switched else paths, 'stop', '-t', '30', 'web', 'api', 'outbox', 'api-image-outbox')
            r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
            print('INTAKE_CLOSED_EXECUTOR_STATE_REQUIRES_INSPECTION', flush=True)
            raise
        # No domestic intake was opened. Keep schema 0027 (additive) and restore applications.
        r.compose(new, 'stop', '-t', '30', 'web', 'api', 'outbox', 'api-image-outbox')
        if switched:
            assert r.pending() == 0
            r.worker(helper, 'api-drain')
            r.compose(new, 'stop', '-t', '30', 'api-image-worker', 'image-variants')
            r.worker(helper, 'native-stop')
            dropin = Path('/etc/systemd/system/hengxin-vps-codex-worker.service.d/90-overseas-release.conf')
            if (backup_dir / dropin.name).exists():
                shutil.copy2(backup_dir / dropin.name, dropin)
            else:
                dropin.unlink(missing_ok=True)
            r.run('systemctl', 'daemon-reload')
        if (backup_dir / 'COMPLETE').exists():
            r.restore_front(backup_dir)
        r.run('systemctl', 'start', 'hengxin-vps-codex-worker')
        r.worker(helper, 'native-verify')
        r.compose(paths, 'up', '-d', '--no-deps', '--wait', *r.SERVICES)
        r.worker(helper, 'api-verify')
        r.sql('UPDATE api_image_channel SET paused=false WHERE id=1')
        r.compose(paths, 'up', '-d', '--no-deps', '--wait', 'web')
        print('ROLLED_BACK_APPLICATIONS_SCHEMA_RETAINED', flush=True)
        raise


def main():
    os.umask(0o077)
    release, action = sys.argv[1:3]
    assert re.fullmatch(r'overseas-20261013-[0-9a-f]{7}', release)
    work = Path('/opt/hengxin-releases') / release
    source, manifest, image = validate(work, release)
    if action == 'build': build(work, source, image)
    elif action == 'prepare': prepare(work, source, image, release)
    elif action == 'deploy': deploy(work, source, manifest)
    else: raise ValueError('Unknown deployment action')


if __name__ == '__main__':
    main()
