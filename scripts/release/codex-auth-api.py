"""Persistent two-file API derived image; never rebuild or restart another service."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

import codex_auth_runtime as r

API = 'hengxin-overseas-api-1'
IMAGE = 'hengxin-smart-image-backend:codex-auth-api-20261019'
BASE_TAG = 'hengxin-smart-image-backend:codex-auth-api-base-20261019'
FILES = {'app/overseas/execution/events.py', 'app/overseas/management/monitor.py'}


def inspect():
    return json.loads(r.run('docker', 'inspect', API))[0]


def hashed(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def config_hash(value):
    config = dict(value['Config'])
    for key in ('Image', 'Hostname'):
        config.pop(key, None)
    dynamic = {'com.docker.compose.config-hash', 'com.docker.compose.image',
               'com.docker.compose.project.config_files', 'com.docker.compose.replace'}
    config['Labels'] = {k: v for k, v in config['Labels'].items() if k not in dynamic}
    return hashed(dict(config=config, host=value['HostConfig'], mounts=sorted(value['Mounts'], key=lambda v: v['Destination']),
                       networks=sorted(value['NetworkSettings']['Networks'])))


def other_topology():
    result = r.topology()
    result['containers'] = [row for row in result['containers'] if row.split()[0] != API]
    # Unlike the native cutover, this action must preserve BOTH execution workers.
    result['workers'] = {domain: [str(cwd), pid] for domain in r.DOMAINS
                         for cwd, _, pid in [r.live(domain)]}
    return result


def package(work):
    data = json.loads((work / 'api-patch.json').read_text())
    r.require(set(data) == {'files'} and set(data['files']) == FILES, 'API patch must contain exactly two reviewed files')
    for name, entry in data['files'].items():
        r.require(set(entry) == {'baseline', 'sha256'}, 'Unexpected API patch fields')
        r.require(all(isinstance(v, str) and len(v) == 64 and all(c in '0123456789abcdef' for c in v)
                      for v in entry.values()), 'Invalid API patch hash')
        path = work / 'api-src' / name
        r.require(path.is_file() and not path.is_symlink() and r.digest(path) == entry['sha256'], 'API package checksum mismatch')
    return data['files']


def compose(data, *args, override=None):
    command = ['docker', 'compose', '-p', 'hengxin-overseas', '--env-file', data['env']]
    for path in data['paths'] + ([str(override)] if override else []):
        command += ['-f', path]
    return r.run(*command, *args, timeout=120)


def image_hashes(image):
    code = ('import hashlib,json,pathlib; print(json.dumps({p:hashlib.sha256(pathlib.Path("/app",p)'
            '.read_bytes()).hexdigest() for p in ' + repr(sorted(FILES)) + '}))')
    return json.loads(r.run('docker', 'run', '--rm', '--network', 'none', '--read-only',
                           '--entrypoint', 'python', image, '-B', '-c', code, timeout=40))


def prepare(work):
    r.require(not (work / 'api-prepared.json').exists(), 'Existing API preparation requires inspection')
    files, live = package(work), inspect()
    labels = live['Config']['Labels']
    r.require(labels['com.docker.compose.project'] == 'hengxin-overseas'
              and labels['com.docker.compose.service'] == 'api' and live['State']['Running'], 'Unexpected API identity')
    paths = labels['com.docker.compose.project.config_files'].split(',')
    env = labels['com.docker.compose.project.environment_file']
    r.require(all(Path(p).is_file() and p.startswith('/opt/') for p in paths + [env]), 'Missing original Compose chain')
    data = dict(paths=paths, env=env, id=live['Id'], old_image=live['Image'], config=config_hash(live),
                files=files, manifest=r.digest(work / 'api-patch.json'), other=other_topology(),
                config_files={p: r.digest(p) for p in paths + [env]})
    r.require(image_hashes(live['Image']) == {p: e['baseline'] for p, e in files.items()}, 'API image baseline differs')
    r.require(not r.run('docker', 'images', '-q', IMAGE), 'New API image tag already exists')
    context = work / 'api-build'
    context.mkdir(mode=0o755)
    for name in files:
        destination = context / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work / 'api-src' / name, destination)
    r.run('docker', 'tag', live['Image'], BASE_TAG)
    (context / 'Dockerfile').write_text('FROM ' + BASE_TAG + '\n' + ''.join(
        'COPY --chmod=0644 ' + name + ' /app/' + name + '\n' for name in sorted(files)))
    r.run('docker', 'build', '--network=none', '--pull=false', '-t', IMAGE, str(context), timeout=180)
    data['image'] = r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', IMAGE)
    r.require(r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', BASE_TAG) == live['Image'], 'Base image tag drift')
    r.require(image_hashes(data['image']) == {p: e['sha256'] for p, e in files.items()}, 'Installed image patch mismatch')
    override = work / 'api-overlay.json'
    r.private(override, {'services': {'api': {'image': data['image']}}})
    before = json.loads(compose(data, 'config', '--format', 'json'))
    after = json.loads(compose(data, 'config', '--format', 'json', override=override))
    before['services']['api']['image'] = data['image']
    r.require(before == after, 'API override changes more than its image')
    r.require(other_topology() == data['other'] and inspect()['Id'] == data['id'], 'Production changed during API build')
    r.private(work / 'api-prepared.json', data)
    print('API_PREPARED', data['image'])


def validate(work, require_test=True):
    data = json.loads((work / 'api-prepared.json').read_text())
    r.require(package(work) == data['files'] and r.digest(work / 'api-patch.json') == data['manifest'], 'API manifest drift')
    r.require(all(r.digest(p) == digest for p, digest in data['config_files'].items()), 'Original Compose config drift')
    r.require(image_hashes(data['image']) == {p: e['sha256'] for p, e in data['files'].items()}, 'API installed image drift')
    r.require(json.loads((work / 'api-overlay.json').read_text()) == {'services': {'api': {'image': data['image']}}},
              'API override drift')
    if require_test:
        proof = json.loads((work / 'API_INSTALL_TESTS_PASSED').read_text())
        r.require(proof == {'manifest': data['manifest'], 'image': data['image']}, 'API installed tests not bound to image')
    return data


def test(work):
    data = validate(work, require_test=False)
    smoke = Path(__file__).with_name('codex_auth_api_smoke.py').resolve()
    output = r.run('docker', 'run', '--rm', '--network', 'none', '--read-only',
        '-e', 'PYTHONPATH=/app',
        '--tmpfs', '/tmp:rw,noexec,nosuid', '--mount', 'type=bind,src=' + str(smoke) + ',dst=/tmp/smoke.py,readonly',
        '--entrypoint', 'python', data['image'], '-B', '/tmp/smoke.py', timeout=60)
    r.require(output == 'API_INSTALLED_PUBLIC_ERROR_PROJECTIONS_PASS', 'Installed API smoke failed')
    r.private(work / 'API_INSTALL_TESTS_PASSED', {'manifest': data['manifest'], 'image': data['image']})
    print(output)


def verify(work, data=None):
    data = data or validate(work)
    live = inspect()
    r.require(live['Image'] == data['image'] and live['State']['Running'], 'New API not running')
    r.require(config_hash(live) == data['config'], 'API runtime configuration changed')
    r.require(live['Config']['Labels']['com.docker.compose.project.config_files'].split(',')
              == data['paths'] + [str(work / 'api-overlay.json')], 'Persistent Compose chain missing')
    r.require(other_topology() == data['other'], 'Another container or worker changed')
    r.run('curl', '--retry', '5', '--retry-delay', '1', '--retry-connrefused', '--max-time', '5',
          '-fsS', '-o', '/dev/null', 'http://127.0.0.1:18018/api/overseas/v1/health/ready', timeout=40)
    r.private(work / 'api-stage.json', {'phase': 'verified', 'id': live['Id'], 'image': live['Image']})
    print('API_PATCH_VERIFIED_OTHER_CONTAINERS_AND_WORKERS_UNCHANGED')


def switch(work):
    data = validate(work)
    r.require(not (work / 'api-stage.json').exists(), 'Inspect prior API switch stage before retry')
    live = inspect()
    r.require(live['Id'] == data['id'] and live['Image'] == data['old_image']
              and config_hash(live) == data['config'], 'Original API drift')
    r.require(other_topology() == data['other'], 'Unrelated topology drift')
    r.private(work / 'api-stage.json', {'phase': 'switch-requested'})
    compose(data, 'up', '-d', '--no-deps', '--no-build', 'api', override=work / 'api-overlay.json')
    r.private(work / 'api-stage.json', {'phase': 'started'})
    verify(work, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'test', 'switch', 'verify'))
    parser.add_argument('--work', type=Path, default=r.WORK)
    args = parser.parse_args()
    r.require(os.geteuid() == 0, 'Root required')
    import fcntl
    with (args.work / '.deploy.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            {'prepare': prepare, 'test': test, 'switch': switch, 'verify': verify}[args.action](args.work)
        except BaseException as exc:
            r.private(args.work / 'API_FAILURE.json', {'action': args.action, 'type': type(exc).__name__,
                'recovery': 'Inspect api-stage.json and actual API. Do not restart workers or restore credentials/DB. '
                'Use saved old_image and original paths only after checking current requests; no automatic rollback.'})
            raise


if __name__ == '__main__':
    main()
