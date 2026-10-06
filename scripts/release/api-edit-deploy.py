"""Fixed release deployment with drained workers, durable backup and fail-closed rollback."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

# These repository tooling suites require infra/frontend source, which is deliberately
# absent from the runtime image. They remain covered by the local full-suite run.
REPOSITORY_ONLY_TESTS = ('test_local_codex', 'test_local_codex_control',
    'test_local_codex_ports', 'test_phase11a_checks', 'test_phase11a_environment',
    'test_phase11a_supervisor')


def installed_test_args():
    return ['-m', 'pytest', '-q',
        *('--ignore=tests/' + name + '.py' for name in REPOSITORY_ONLY_TESTS),
        '--deselect=tests/test_contracts.py::test_top_level_fields_match_frontend_interfaces']

spec = importlib.util.spec_from_file_location('runtime', Path(__file__).with_name('api-edit-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def pending():
    return int(r.sql("SELECT (SELECT count(*) FROM job_records WHERE status NOT IN ('succeeded','partial','failed','cancelled')) + (SELECT count(*) FROM api_image_tasks WHERE state NOT IN ('succeeded','failed','partial_failed')) + (SELECT count(*) FROM api_image_items WHERE state NOT IN ('succeeded','failed'))"))


def main():
    os.umask(0o077)
    release, mode = sys.argv[1:3]
    assert re.fullmatch(r'api-edit-20261006-[0-9a-f]{7}', release)
    assert mode in ('build', 'deploy')
    work = Path('/opt/hengxin-releases') / release
    source, backup = work / 'src', Path('/opt/hengxin-backups') / release
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['migration'] == '0023'
    assert manifest['frontendVersion'] == '0.2.17'
    paths, image = r.prepare(work, manifest)
    new = [*paths, work / 'api-override.yaml']
    helper = source / 'scripts/release/image-inputs-worker.py'
    def api(action):
        for attempt in range(12 if action == 'api-verify' else 1):
            try:
                with helper.open() as stream:
                    r.run('docker', 'exec', '-i', r.PREFIX + 'api-image-worker-1', 'python', '-', action, '300', stdin=stream)
                return
            except subprocess.CalledProcessError:
                if action != 'api-verify' or attempt == 11: raise
                time.sleep(3)
    def native(action):
        r.run('python3', str(helper), 'run-native-' + action, '120')
    if mode == 'build':
        r.run('docker', 'build', '-t', image, '-f', str(source / 'infra/Dockerfile.backend'), str(source))
        with (work / 'installation-tests.log').open('w') as log:
            subprocess.run(['docker', 'run', '--rm', '--init', '--network', 'none', '--entrypoint', 'python',
                '-e', 'APP_ENV=test', '-e', 'ENABLE_DEV_IDENTITY=false', image,
                *installed_test_args()], stdout=log, stderr=subprocess.STDOUT, check=True)
        (work / 'INSTALL_TEST_IMAGE_ID').write_text(r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', image, capture=True))
        print('BUILD_AND_INSTALL_TESTS_PASS', flush=True)
        return
    assert (work / 'INSTALL_TEST_IMAGE_ID').read_text() == r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', image, capture=True)
    assert r.sql('SELECT version_num FROM alembic_version') == '0022'
    assert r.sql('SELECT paused FROM api_image_channel WHERE id=1') == 'f' and pending() == 0
    assert not backup.exists()
    closed = drained = native_changed = new_started = front_changed = opening = False
    try:
        closed = True
        r.compose(paths, 'stop', '-t', '30', 'web', 'api', 'outbox', 'api-image-outbox')
        r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
        api('api-drain')
        r.compose(paths, 'stop', '-t', '30', 'api-image-worker')
        native('stop')
        assert pending() == 0
        drained = True
        r.compose(paths, 'stop', '-t', '30', 'image-variants')
        r.backup(work, backup)
        print('BACKUP_COMPLETE', flush=True)
        r.compose(new, 'run', '--rm', '--no-deps', 'migrate')
        assert r.sql('SELECT version_num FROM alembic_version') == '0023'
        assert r.sql('SELECT enabled FROM capacity_gate WHERE id=1') == 'f'
        native_changed = True
        r.install_native(source)
        r.run('uv', 'pip', 'check', '--python', str(r.NATIVE / '.venv/bin/python'))
        r.run('systemctl', 'start', 'hengxin-vps-codex-worker')
        native('verify')
        new_started = True
        r.compose(new, 'up', '-d', '--no-deps', '--wait', 'api')
        r.compose(new, 'up', '-d', '--no-deps', 'api-image-worker', 'outbox', 'api-image-outbox', 'image-variants')
        api('api-verify')
        r.run('curl', '--retry', '8', '--retry-delay', '2', '-fsS', 'http://127.0.0.1:18008/api/v1/health/ready')
        front_changed = True
        r.publish_frontend(source, work, manifest, paths)
        r.sql('UPDATE api_image_channel SET paused=false WHERE id=1')
        opening = True
        r.compose(new, 'up', '-d', '--no-deps', '--wait', 'web')
        r.run('docker', 'exec', r.PREFIX + 'web-1', 'nginx', '-s', 'reload')
        r.run('curl', '--retry', '8', '--retry-delay', '2', '-fsS', '-o', '/dev/null', 'http://127.0.0.1:18080/')
        print('DEPLOY_COMPLETE ' + release + ' backup=' + str(backup), flush=True)
    except BaseException:
        if not closed: raise
        if opening:
            # New API attempts may now exist; retain the new executor until inspected.
            try:
                r.compose(new, 'stop', '-t', '30', 'web', 'api', 'outbox', 'api-image-outbox')
            finally:
                r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
            print('POST_OPEN_FAILURE_NEW_CODE_RETAINED_INTAKE_CLOSED', flush=True)
            raise
        if not drained:
            try:
                r.compose(paths, 'stop', '-t', '30', 'web', 'api', 'outbox', 'api-image-outbox')
            finally:
                try:
                    r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
                finally:
                    print('DRAIN_UNCERTAIN_NO_WORKER_RESTART_CHECK_INTAKE', flush=True)
            raise
        try:
            r.compose(new, 'stop', '-t', '30', 'web', 'api', 'outbox', 'api-image-outbox', 'image-variants')
            r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
            if new_started:
                if r.inspect('api-image-worker')['State']['Running']: api('api-drain')
                r.compose(new, 'stop', '-t', '30', 'api-image-worker')
            if native_changed:
                assert (backup / 'COMPLETE').is_file()
                if r.run('systemctl', 'show', 'hengxin-vps-codex-worker', '-p', 'ActiveState', '--value', capture=True) == 'active': native('stop')
                os.replace(r.NATIVE / 'app', r.NATIVE / ('app.failed-' + release))
                r.run('cp', '-a', str(backup / 'native-app'), str(r.NATIVE / 'app'))
            r.run('systemctl', 'start', 'hengxin-vps-codex-worker')
            native('verify')
            if front_changed:
                for name in ('nginx.vps.conf', 'nginx.media.conf'):
                    target = r.APP / 'infra' / name
                    if (backup / name).exists(): shutil.copyfile(backup / name, target)
                    else: target.unlink(missing_ok=True)
                for name in ('index.html', 'index.html.gz'):
                    target = r.APP / 'frontend/dist' / name
                    if (backup / name).exists(): shutil.copy2(backup / name, target)
                    else: target.unlink(missing_ok=True)
                shutil.copy2(backup / 'frontend-package.json', r.APP / 'frontend/package.json')
                for name in ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json', 'API_TEXT_RELEASE.json', 'API_EDIT_RELEASE.json'):
                    if (backup / name).exists(): shutil.copy2(backup / name, r.APP / name)
                    else: (r.APP / name).unlink(missing_ok=True)
            r.compose(paths, 'up', '-d', '--no-deps', '--wait', *r.SERVICES)
            api('api-resume'); api('api-verify')
            r.run('curl', '--retry', '5', '--retry-delay', '2', '-fsS', 'http://127.0.0.1:18008/api/v1/health/ready')
            r.sql('UPDATE api_image_channel SET paused=false WHERE id=1')
            r.compose(paths, 'up', '-d', '--no-deps', '--wait', 'web')
            print('ROLLED_BACK_CODE_AND_CONFIG_SCHEMA_RETAINED', flush=True)
        except BaseException:
            try:
                r.compose(new, 'stop', '-t', '30', 'web', 'api', 'outbox', 'api-image-outbox')
            finally:
                try:
                    r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
                finally:
                    print('ROLLBACK_BLOCKED_INTAKE_CLOSED backup=' + str(backup), flush=True)
        raise


if __name__ == '__main__':
    main()
