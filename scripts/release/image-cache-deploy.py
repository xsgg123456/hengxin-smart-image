"""Prepare derived API, drain overseas worker, switch only approved API/static assets."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import time

spec = importlib.util.spec_from_file_location('image_runtime', Path(__file__).with_name('image-cache-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def state(work, tested=False):
    data = json.loads((work / 'prepared.json').read_text())
    source = Path(data['source'])
    r.require(r.digest(source / 'release.json') == data['manifest'], 'Manifest drift')
    r.verify_package(source)
    r.require(r.topology() == data['other'], 'Unrelated services changed')
    r.require(all(r.digest(p) == h for p, h in data['compose']['files'].items()), 'Compose baseline drift')
    for saved in data['units'].values():
        r.require(all(r.digest(p) == h for p, h in saved['files'].items()), 'Original service configuration drift')
    r.require(r.hashes(data['image']) == {n: v['sha256'] for n, v in data['patch'].items()}, 'API image drift')
    r.require(r.digest(work / 'api-overlay.json') == data['overlayHash'], 'Overlay drift')
    if tested:
        proof = json.loads((work / 'INSTALL_TESTS_PASSED').read_text())
        r.require(proof == {'manifest': data['manifest'], 'image': data['image']}, 'Installed test evidence absent')
    return data, source


def prepare(work, source):
    r.require(not (work / 'prepared.json').exists(), 'Preparation exists; inspect before retry')
    manifest, live = r.verify_package(source), r.inspect()
    r.require(live['State']['Running'] and live['Image'] == manifest['api']['image'], 'API baseline drift')
    r.require(r.hashes(live['Image']) == {n:v['baseline'] for n,v in manifest['api']['files'].items()}, 'API source drift')
    data = dict(source=str(source), manifest=r.digest(source / 'release.json'), other=r.topology(),
                oldId=live['Id'], oldImage=live['Image'], compose=r.a.compose_info(live),
                patch=manifest['api']['files'], units={u:r.unit_state(u) for u in r.UNITS})
    for unit in r.UNITS:
        r.require(not r.drop_path(unit).exists(), 'Service override already exists')
    data['node'] = r.a.worker_probe('overseas', 'verify', work)['node']
    before = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json'))
    r.a.check_live_config(live, before)
    context = work / 'api-build'
    context.mkdir(mode=0o755)
    for name in r.FILES:
        target = context / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / 'api' / name, target)
    for path in context.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    tag = 'hengxin-smart-image-backend:' + manifest['release']
    r.require(not r.run('docker', 'images', '-q', tag), 'Image tag exists')
    r.run('docker', 'tag', live['Image'], tag + '-base')
    (context / 'Dockerfile').write_text('FROM ' + tag + '-base\n' + ''.join(
        'COPY ' + name + ' /app/' + name + '\n' for name in sorted(r.FILES)))
    r.run('docker', 'build', '--network=none', '--pull=false', '-t', tag, str(context), timeout=180)
    data['image'] = r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', tag)
    r.require(r.hashes(data['image']) == {n:v['sha256'] for n,v in data['patch'].items()}, 'Installed patch mismatch')
    overlay = work / 'api-overlay.json'
    r.private(overlay, {'services': {'api': {'image': data['image'], 'environment': r.ENV}}})
    expected = json.loads(json.dumps(before))
    expected['services']['api']['image'] = data['image']
    expected['services']['api'].setdefault('environment', {}).update(r.ENV)
    after = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json', overlay=overlay))
    r.require(expected == after, 'Overlay changes unrelated settings')
    data['overlayHash'] = r.digest(overlay)
    r.require(r.topology() == data['other'], 'Production changed during preparation')
    r.private(work / 'prepared.json', data)
    r.private(work / 'RECOVERY.txt', 'Inspect stages and live PID/queues before action.\n'
        'Worker rollback: cancel consumer, prove idle, stop, remove ONLY this release drop-ins, '
        'daemon-reload then restart outbox/worker. Never interrupt active jobs.\n'
        'API rollback: use saved original Compose chain and immutable oldImage; retain account sockets.\n'
        'Static rollback: image-cache-frontend.py rollback, retained hashed assets.\n'
        'Never restore DB, credentials, tasks or conversations. No automatic rollback.\n')
    return 'PREPARED_NO_RUNNING_SERVICE_CHANGED'


def test(work):
    data, source = state(work)
    # Reuse the image's installed pytest; no production network, mounts or databases.
    test_image = data['image']
    command = ['docker', 'run', '--rm', '--network=none', '--read-only', '--tmpfs', '/tmp:rw,nosuid',
               '--mount', 'type=bind,src=' + str(source / 'tests') + ',dst=/app/tests,readonly',
               '-e', 'PYTHONPATH=/app', '--entrypoint', 'python', test_image,
               '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
               '/app/tests/test_overseas_image_cache.py', '/app/tests/test_overseas_thumbnail_limits.py',
               '/app/tests/test_overseas_image_cache_settings.py',
               '/app/tests/test_overseas_management_freeze.py', '/app/tests/test_overseas_pictures.py',
               '/app/tests/test_overseas_pictures_protocol.py', '/app/tests/test_studio_image_preview.py']
    output = r.run(*command, timeout=180)
    r.require('passed' in output and 'failed' not in output and 'skipped' not in output, 'Installed image tests incomplete')
    r.private(work / 'installed-tests.txt', output)
    r.private(work / 'INSTALL_TESTS_PASSED', {'manifest':data['manifest'], 'image':data['image']})
    return output


def workers(work):
    data, _ = state(work, tested=True)
    r.require(not (work / 'overseas-stage.json').exists(), 'Inspect previous worker attempt')
    r.require({u:r.unit_state(u) for u in r.UNITS} == data['units'], 'Worker baseline drift')
    for unit in r.UNITS:
        r.require(not r.drop_path(unit).exists(), 'Unexpected worker override')
    # Existing tested drain cancels intake, checks Celery and DB twice, restores intake if busy.
    r.a.worker_probe('overseas', 'drain-stop', work)
    r.require(json.loads((work / 'overseas-stage.json').read_text())['phase'] == 'stopped', 'No idle stop proof')
    r.private(work / 'workers-stage.json', {'phase':'worker-stopped'})
    r.run('systemctl', 'stop', r.UNITS[1], timeout=45)
    r.require(r.run('systemctl','show',r.UNITS[1],'-p','MainPID','--value') == '0', 'Outbox stop unconfirmed')
    # Append EnvironmentFile to override any earlier EnvironmentFile values safely.
    env_path = work / 'timeout.env'
    r.private(env_path, ''.join(k + '=' + v + '\n' for k,v in r.ENV.items()))
    for unit in r.UNITS:
        path = r.drop_path(unit)
        with path.open('x') as out:
            out.write('[Service]\nEnvironmentFile=' + str(env_path) + '\n')
        path.chmod(0o644)
    r.private(work / 'workers-stage.json', {'phase':'overrides-written'})
    r.run('systemctl', 'daemon-reload')
    r.run('systemctl', 'start', r.UNITS[1])
    r.run('systemctl', 'start', r.UNITS[0])
    verify_workers(work, data)
    return 'OVERSEAS_WORKERS_7200_7800_VERIFIED'


def verify_workers(work, data):
    deadline = time.monotonic() + 40
    while True:
        try:
            remaining = deadline - time.monotonic()
            r.require(remaining > 0, 'Worker readiness deadline exceeded')
            result = r.a.worker_probe('overseas', 'verify', work, timeout=min(15,remaining))
            r.require(result['node'] == data['node'], 'Worker node changed')
            r.require(time.monotonic() < deadline, 'Worker deadline exceeded')
            break
        except (RuntimeError, __import__('subprocess').TimeoutExpired):
            r.require(time.monotonic() < deadline, 'Worker not ready; inspect stage')
            time.sleep(0.5)
    for unit in r.UNITS:
        current = r.unit_state(unit)
        r.require(current['cwd'] == data['units'][unit]['cwd'], 'Worker source changed')
        env = dict(v.decode().split('=',1) for v in (Path('/proc')/str(current['pid'])/'environ').read_bytes().split(b'\0') if v)
        r.require(all(env.get(k) == v for k,v in r.ENV.items()), 'Worker timeout configuration missing')
    r.require(r.topology() == data['other'], 'Unrelated service changed')
    r.private(work / 'workers-stage.json', {'phase':'verified', 'units':{u:r.unit_state(u) for u in r.UNITS}})


def api(work):
    data, _ = state(work, tested=True)
    r.require(not (work / 'api-stage.json').exists(), 'Inspect previous API attempt')
    r.require(r.inspect()['Id'] == data['oldId'], 'Original API changed')
    verify_workers(work, data)
    r.private(work / 'api-stage.json', {'phase':'switch-requested'})
    r.a.compose(data['compose'], 'up', '-d', '--no-deps', '--no-build', 'api', overlay=work/'api-overlay.json')
    verify(work)
    return 'API_0.2.55_VERIFIED'


def verify(work):
    data, _ = state(work, tested=True)
    verify_workers(work, data)
    live = r.inspect()
    r.require(live['Image'] == data['image'] and live['State']['Running'], 'Expected API not running')
    config = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json', overlay=work/'api-overlay.json'))
    r.a.check_live_config(live, config)
    r.require(live['Config']['Labels']['com.docker.compose.project.config_files'].split(',') ==
              data['compose']['paths'] + [str(work/'api-overlay.json')], 'Compose overlay not retained')
    r.readiness('http://127.0.0.1:18018/api/overseas/v1/health/ready')
    r.private(work / 'api-stage.json', {'phase':'verified', 'id':live['Id'], 'image':live['Image']})
    return 'API_AND_WORKERS_VERIFIED'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','test','workers','api','verify'))
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    r.require(os.geteuid() == 0, 'Root required')
    os.umask(0o077)
    args.work.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (args.work/'.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            value = prepare(args.work,args.source.resolve()) if args.action == 'prepare' else globals()[args.action](args.work)
            print(value)
        except BaseException as exc:
            r.private(args.work/'FAILURE.json', {'action':args.action,'errorType':type(exc).__name__,
                'recovery':'Inspect saved stages and RECOVERY.txt. No forced stop or automatic rollback.'})
            raise


if __name__ == '__main__':
    main()
