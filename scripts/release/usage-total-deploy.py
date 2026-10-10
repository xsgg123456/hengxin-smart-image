"""Build or deploy the fixed usage-total release, replacing only HTTP API and frontend."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

spec = importlib.util.spec_from_file_location('usage_total_runtime', Path(__file__).with_name('usage-total-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
REPOSITORY_ONLY_TESTS = ('test_local_codex', 'test_local_codex_control', 'test_local_codex_ports',
    'test_phase11a_checks', 'test_phase11a_environment', 'test_phase11a_supervisor')


def installed_test_args():
    return ['-m', 'pytest', '-q', *('--ignore=tests/' + name + '.py' for name in REPOSITORY_ONLY_TESTS),
            '--deselect=tests/test_contracts.py::test_top_level_fields_match_frontend_interfaces']


def manifest_for(source, release):
    assert re.fullmatch(r'usage-total-20261010-[0-9a-f]{7}', release)
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['migration'] == '0026'
    assert manifest['frontendVersion'] == '0.2.21'
    assert json.loads((source / 'frontend/package.json').read_text())['version'] == '0.2.21'
    assert manifest['files'] and 'frontend/dist/index.html' in manifest['files']
    r.hashes(source, manifest)
    return manifest


def image_id(image):
    return r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', image, capture=True)


def evidence(source, image):
    return {'image': image_id(image), 'manifest': hashlib.sha256((source / 'release.json').read_bytes()).hexdigest()}


def build(work, source, image):
    for name in ('INSTALL_TEST_IMAGE_ID', 'INSTALL_TEST_EVIDENCE.json'):
        (work / name).unlink(missing_ok=True)
    r.run('docker', 'build', '-t', image, '-f', str(source / 'infra/Dockerfile.backend'), str(source))
    tested = image_id(image)
    with (work / 'installation-tests.log').open('w') as log:
        subprocess.run(['docker', 'run', '--rm', '--init', '--network', 'none', '--entrypoint', 'python',
            '-e', 'APP_ENV=test', '-e', 'ENABLE_DEV_IDENTITY=false', tested, *installed_test_args()],
            stdout=log, stderr=subprocess.STDOUT, check=True)
    proof = evidence(source, image)
    assert proof['image'] == tested
    (work / 'INSTALL_TEST_IMAGE_ID').write_text(tested)
    r.private(work / 'INSTALL_TEST_EVIDENCE.json', proof)


def deploy(work, source, backup, manifest, image):
    assert (work / 'INSTALL_TEST_IMAGE_ID').read_text() == image_id(image)
    assert json.loads((work / 'INSTALL_TEST_EVIDENCE.json').read_text()) == evidence(source, image)
    paths, prepared_image, old = r.prepare(work, manifest)
    assert image == prepared_image
    before = r.identity()
    r.backup(work, backup, before)
    r.unchanged(before)
    new = [*paths, work / 'api-override.yaml']
    changed = front_changed = False
    try:
        changed = True  # A failed compose command may already have replaced API.
        r.compose(new, 'up', '-d', '--no-deps', '--wait', '--timeout', '120', 'api')
        live = r.inspect('api')
        assert live['Image'] == image_id(image)
        assert r.api_settings(live) == r.api_settings(old), 'API runtime settings drifted'
        r.ready()
        r.unchanged(before)
        # Resolve the replacement API address immediately; keep existing nginx connections.
        r.reload_nginx()
        verifier = str(source / 'scripts/release/usage-total-verify.py')
        r.run('python3', verifier, manifest['release'], '--api-only')
        front_changed = True
        r.publish(source, work, manifest, paths)
        r.run('python3', verifier, manifest['release'])
        r.unchanged(before)
    except BaseException:
        rollback_errors = []
        try:
            if changed:
                try:
                    # Ensure the original tag still resolves to the exact original image.
                    assert image_id(old['Config']['Image']) == old['Image'], 'Original API tag drifted'
                    r.compose(paths, 'up', '-d', '--no-deps', '--wait', '--timeout', '120', 'api')
                    live = r.inspect('api')
                    assert live['Image'] == old['Image'] and r.api_settings(live) == r.api_settings(old)
                    r.ready()
                except BaseException as error: rollback_errors.append(error)
            if front_changed:
                try: r.restore(backup)
                except BaseException as error: rollback_errors.append(error)
            if changed:
                try: r.reload_nginx()
                except BaseException as error: rollback_errors.append(error)
        finally:
            r.unchanged(before)
        if rollback_errors:
            raise RuntimeError('API/frontend rollback incomplete; inspect private backup ' + str(backup)) from rollback_errors[0]
        raise


def main():
    os.umask(0o077)
    release, mode = sys.argv[1:3]
    assert mode in ('build', 'deploy')
    work = Path('/opt/hengxin-releases') / release
    source = work / 'src'
    manifest = manifest_for(source, release)
    image = 'hengxin-smart-image-backend:' + release
    if mode == 'build': build(work, source, image)
    else: deploy(work, source, Path('/opt/hengxin-backups') / release, manifest, image)
    print(mode.upper() + '_COMPLETE ' + release, flush=True)


if __name__ == '__main__':
    main()
