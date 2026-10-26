"""Prepare/test/start/API/worker/frontend phases. Rollback never restores credentials or databases."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

spec = importlib.util.spec_from_file_location('account_runtime', Path(__file__).with_name('account-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def state(work):
    value = json.loads((work / 'prepared.json').read_text())
    source = Path(value['source'])
    r.require(r.digest(source / 'release.json') == value['manifest'], 'Manifest drift')
    r.verify_package(source)
    for name, expected in value.get('hostFiles', {}).items():
        r.require(r.digest(Path(value['host']) / name) == expected, 'Installed daemon source drift')
    r.require(r.topology() == value['other'], 'Unrelated production topology changed')
    for data in value['apis'].values():
        r.require(all(r.digest(p) == h for p,h in data['compose']['files'].items()), 'Compose source drift')
    for saved in value['workers'].values():
        r.require(all(r.digest(p) == h for p,h in saved['files'].items()), 'Original worker configuration drift')
    return value, source


def prepare(work, source):
    r.require(not (work / 'prepared.json').exists(), 'Preparation exists; inspect before retry')
    manifest = r.verify_package(source)
    r.require(not (Path('/etc/systemd/system') / r.SERVICE).exists(), 'Account service already installed')
    r.require(not r.PRIVATE.exists(), 'Private account store already exists; inspect before migration')
    r.require(r.run('getent', 'group', 'hengxin-codex-auth').split(':')[2] == '986', 'Socket GID drift')
    data = dict(source=str(source), manifest=r.digest(source / 'release.json'), other=r.topology(), apis={}, workers={})
    for domain in r.DOMAINS:
        live = r.inspect(domain)
        r.require(live['State']['Running'] and live['Image'] == manifest['apis'][domain]['image'], 'API baseline drift')
        r.require(r.run('docker', 'exec', r.DOMAINS[domain]['container'], 'id', '-u') == '10001', 'API UID drift')
        r.require(not r.drop_path(domain).exists(), 'Worker override already exists')
        worker = r.worker(domain)
        worker['node'] = r.worker_probe(domain, 'verify', work)['node']
        worker['unitHash'] = __import__('hashlib').sha256(r.run('systemctl', 'cat', r.DOMAINS[domain]['unit']).encode()).hexdigest()
        worker_files = set()
        for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles'):
            worker_files.update(part for part in r.run('systemctl','show',r.DOMAINS[domain]['unit'],'-p',key,'--value').split()
                                if part.startswith('/'))
        worker['files'] = {p:r.digest(p) for p in worker_files}
        data['workers'][domain] = worker
        compose = r.compose_info(live)
        old = json.loads(r.compose(compose, 'config', '--format', 'json'))
        r.check_live_config(live, old)
        files = manifest['apis'][domain]['files']
        r.require(r.api_hashes(live['Image']) == {n:e['baseline'] for n,e in files.items()}, 'API source baseline drift')
        context = work / (domain + '-build')
        context.mkdir(mode=0o755)
        for name in files:
            target = context / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / 'api' / domain / name, target)
        tag = 'hengxin-smart-image-backend:' + manifest['release'] + '-' + domain
        r.require(not r.run('docker', 'images', '-q', tag + '-base'), 'Base tag already exists')
        r.run('docker', 'tag', live['Image'], tag + '-base')
        r.require(r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', tag + '-base') == live['Image'], 'Base tag drift')
        (context / 'Dockerfile').write_text('FROM ' + tag + '-base\n' + ''.join(
            'COPY --chmod=0644 ' + name + ' /app/' + name + '\n' for name in sorted(files)))
        r.require(not r.run('docker', 'images', '-q', tag), 'Image tag already exists')
        r.run('docker', 'build', '--network=none', '--pull=false', '-t', tag, str(context), timeout=180)
        image = r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', tag)
        r.require(r.api_hashes(image) == {n:e['sha256'] for n,e in files.items()}, 'Installed patch mismatch')
        prefix = r.DOMAINS[domain]['prefix']
        overlay = {'services': {'api': {'image': image,
            'environment': {prefix + 'CODEX_ACCOUNT_MANAGEMENT_SOCKET': '/run/hengxin-codex-account/control.sock'},
            'group_add': ['986'], 'volumes': [{'type': 'bind', 'source': str(r.RUNTIME / domain),
                  'target': '/run/hengxin-codex-account', 'read_only': True, 'bind': {'create_host_path': False}}]}}}
        path = work / (domain + '-overlay.json')
        r.private(path, overlay)
        new = json.loads(r.compose(compose, 'config', '--format', 'json', overlay=path))
        expected = json.loads(json.dumps(old))
        api = expected['services']['api']
        api['image'] = image
        api.setdefault('environment', {})[prefix + 'CODEX_ACCOUNT_MANAGEMENT_SOCKET'] = '/run/hengxin-codex-account/control.sock'
        api['group_add'] = list(dict.fromkeys(api.get('group_add', []) + ['986']))
        api.setdefault('volumes', []).append(overlay['services']['api']['volumes'][0])
        api['volumes'].sort(key=lambda v:v['target'])
        new['services']['api']['volumes'].sort(key=lambda v:v['target'])
        r.require(expected == new, 'Overlay changed unrelated Compose settings')
        data['apis'][domain] = dict(id=live['Id'], oldImage=live['Image'], image=image, compose=compose,
                                     overlayHash=r.digest(path), files=files)
    # Keep public daemon code outside the root-only release evidence directory.
    host = Path('/opt/hengxin-account-releases') / manifest['release']
    host.parent.mkdir(mode=0o755, exist_ok=True)
    r.require(not host.exists(), 'Installed daemon target already exists')
    host.mkdir(mode=0o755)
    shutil.copytree(source / 'daemon', host / 'daemon')
    shutil.copytree(source / 'tests', host / 'tests')
    for path in (host, *host.rglob('*')):
        path.chmod(0o755 if path.is_dir() else 0o644)
    data['host'] = str(host)
    data['hostFiles'] = {p.relative_to(host).as_posix():r.digest(p) for p in host.rglob('*.py')}
    r.private(work / r.SERVICE, r.service_unit(host))
    data['unitHash'] = r.digest(work / r.SERVICE)
    r.run('systemd-analyze', 'verify', str(work / r.SERVICE))
    r.require(r.topology() == data['other'], 'Topology changed during preparation')
    r.private(work / 'prepared.json', data)
    r.private(work / 'RECOVERY.txt', 'API rollback uses only saved immutable image and original Compose files.\n'
        'Worker rollback cancels intake and drains again before removing only this release drop-in.\n'
        'Never rollback a worker after independent account activation/removal: old broker has shared identity.\n'
        'Do not stop account service while any worker uses its socket. Keep private account store permanently.\n'
        'Never restore credentials, refresh tokens, databases or task state. No automatic rollback.\n')
    return 'PREPARED_NO_LIVE_SERVICE_CHANGED'


def test(work, test_python):
    data, _ = state(work)
    return r.module('account-installed-tests').test_installed(work, data, test_python, r)


def validated(work):
    data, source = state(work)
    expected = dict(manifest=data['manifest'], images={d:v['image'] for d,v in data['apis'].items()})
    r.require(json.loads((work / 'INSTALL_TESTS_PASSED').read_text()) == expected, 'Installation evidence absent')
    return data, source


def start(work):
    data, source = validated(work)
    path = Path('/etc/systemd/system') / r.SERVICE
    r.require(r.digest(work / r.SERVICE) == data['unitHash'], 'Account service unit drift')
    r.require(not path.exists() and not r.PRIVATE.exists(), 'Service/store exists; inspect partial installation')
    r.PRIVATE.mkdir(mode=0o700)
    os.chown(r.PRIVATE, 1001, 986)
    shutil.copyfile(work / r.SERVICE, path)
    path.chmod(0o644)
    r.private(work / 'service-stage.json', {'phase': 'start-requested'})
    r.run('systemctl', 'daemon-reload')
    r.run('systemctl', 'enable', '--now', r.SERVICE)
    deadline = time.monotonic() + 20
    sockets = [r.RUNTIME / 'worker.sock', *(r.RUNTIME / d / 'control.sock' for d in r.DOMAINS)]
    while not all(p.is_socket() for p in sockets):
        r.require(time.monotonic() < deadline, 'Account sockets not ready')
        time.sleep(0.25)
    # Read-only control status, from the actual API UID; does not refresh credentials.
    for domain in r.DOMAINS:
        control_status(Path(data['host']), domain)
        broker_access(Path(data['host']), domain)
    r.private(work / 'service-stage.json', {'phase': 'ready'})
    return 'ACCOUNT_SERVICE_READY'


def control_status(source, domain):
    code = ("import socket,time; from app.execution.credential_broker_client import send,receive; "
            "s=socket.socket(socket.AF_UNIX); s.settimeout(5); s.connect(" + repr(str(r.RUNTIME / domain / 'control.sock')) + "); "
            "send(s,{'action':'status','actor':{'id':'00000000-0000-0000-0000-000000000001','name':'发布核查'}},16384,time.monotonic()+5); "
            "x=receive(s,131072,time.monotonic()+5); assert 'data' in x; print(x['data']['revision'])")
    return int(r.run('setpriv', '--reuid=10001', '--regid=10001', '--groups=986', '/usr/bin/python3', '-B', '-c', code,
                     cwd=source / 'daemon'))


def broker_access(host, domain):
    config = r.DOMAINS[domain]
    code = ("from app.execution.credential_broker_client import request_credentials; "
            "a=request_credentials(" + repr(str(r.RUNTIME / 'worker.sock')) + ",600); "
            "assert a['tokens']['access_token'] and not a['tokens'].get('refresh_token'); print('ACCESS_ONLY_PASS')")
    output = r.run('setpriv', '--reuid='+str(config['uid']), '--regid='+str(config['gid']), '--groups=986',
                   '/usr/bin/python3', '-B', '-c', code, cwd=host / 'daemon', timeout=90)
    r.require(output == 'ACCESS_ONLY_PASS', 'Worker UID access-only handshake failed')


def switch_api(work, domain, rollback=False):
    data, source = validated(work)
    saved, live = data['apis'][domain], r.inspect(domain)
    workers = {d:r.worker(d) for d in r.DOMAINS}
    path = work / (domain + '-overlay.json')
    r.require(r.digest(path) == saved['overlayHash'], 'API overlay drift')
    if rollback:
        r.require(live['Image'] == saved['image'], 'Rollback requires this release API')
        # The original chain still points at the original immutable image ID/tag.
        target = saved['oldImage']
        old = json.loads(r.compose(saved['compose'], 'config', '--format', 'json'))
        r.require(r.run('docker','image','inspect','--format','{{.Id}}',old['services']['api']['image']) == target, 'Old image tag drift')
        overlay = None
    else:
        r.require(live['Id'] == saved['id'] and live['Image'] == saved['oldImage'], 'Original API drift')
        for business in r.DOMAINS:
            stage = json.loads((work / (business + '-stage.json')).read_text())
            current = r.worker(business)
            r.require(stage.get('phase') == 'verified' and stage.get('pid') == current['pid'],
                      'Both workers must use the account service before exposing account changes')
            runtime_env = (Path('/proc') / str(current['pid']) / 'environ').read_bytes().split(b'\0')
            wanted = r.DOMAINS[business]['prefix'] + 'CODEX_AUTH_BROKER_SOCKET=' + str(r.RUNTIME / 'worker.sock')
            r.require(wanted.encode() in runtime_env, 'Worker account socket drift')
        control_status(Path(data['host']), domain)
        broker_access(Path(data['host']), domain)
        r.require(r.api_hashes(saved['image']) == {n:e['sha256'] for n,e in saved['files'].items()}, 'API image drift')
        target, overlay = saved['image'], path
    r.private(work / (domain + '-api-stage.json'), {'phase': 'rollback-requested' if rollback else 'switch-requested'})
    r.compose(saved['compose'], 'up', '-d', '--no-deps', '--no-build', 'api', overlay=overlay)
    live = r.inspect(domain)
    r.require(live['Image'] == target and live['State']['Running'], 'Expected API image not running')
    expected = json.loads(r.compose(saved['compose'], 'config', '--format', 'json', overlay=overlay))
    r.check_live_config(live, expected)
    r.require(live['HostConfig'].get('GroupAdd') == expected['services']['api'].get('group_add'), 'API groups drift')
    url = 'http://127.0.0.1:' + ('18008/api/v1' if domain == 'domestic' else '18018/api/overseas/v1') + '/health/ready'
    r.run('curl', '--retry', '5', '--retry-delay', '1', '--retry-connrefused', '--max-time', '5', '-fsS', '-o', '/dev/null', url)
    r.require({d:r.worker(d) for d in r.DOMAINS} == workers, 'API change disturbed workers')
    r.require(r.topology() == data['other'], 'Unrelated services changed')
    r.private(work / (domain + '-api-stage.json'), {'phase': 'rolled-back' if rollback else 'verified', 'id':live['Id']})
    return 'API_ROLLED_BACK' if rollback else 'API_VERIFIED'


def switch_worker(work, domain, rollback=False):
    data, source = validated(work)
    saved, config = data['workers'][domain], r.DOMAINS[domain]
    current = r.worker(domain)
    r.require(current['cwd'] == saved['cwd'], 'Worker source directory changed')
    path = r.drop_path(domain)
    override = '[Service]\nEnvironment=' + config['prefix'] + 'CODEX_AUTH_BROKER_SOCKET=' + str(r.RUNTIME / 'worker.sock') + '\n'
    if rollback:
        r.require(path.read_text() == override, 'Worker release override drift')
        r.require(all(r.inspect(b)['Image'] == data['apis'][b]['oldImage'] for b in r.DOMAINS),
                  'Rollback both APIs first to close account changes before worker rollback')
        # Old broker always uses the shared master: forbid undoing an independently chosen identity.
        for business in r.DOMAINS:
            r.require(control_status(Path(data['host']), business) == 0, 'Account revision changed; old shared broker rollback unsafe')
    else:
        r.require(not path.exists() and current['pid'] == saved['pid'], 'Worker baseline changed')
        r.require(__import__('hashlib').sha256(r.run('systemctl','cat',config['unit']).encode()).hexdigest() == saved['unitHash'], 'Worker unit drift')
        control_status(Path(data['host']), domain)
        broker_access(Path(data['host']), domain)
    r.private(work / (domain + '-stage.json'), {'phase': 'draining'})
    r.worker_probe(domain, 'drain-stop', work)
    r.require(json.loads((work / (domain + '-stage.json')).read_text())['phase'] == 'stopped', 'No proven idle stop')
    if rollback:
        for business in r.DOMAINS:
            r.require(control_status(Path(data['host']), business) == 0, 'Account changed during drain; worker remains stopped')
        path.unlink()
    else:
        with path.open('x') as stream:
            stream.write(override)
        path.chmod(0o644)
    r.private(work / (domain + '-stage.json'), {'phase': 'override-restored' if rollback else 'override-written'})
    r.run('systemctl', 'daemon-reload')
    r.run('systemctl', 'start', config['unit'])
    deadline = time.monotonic() + 35
    while True:
        try:
            remaining = deadline - time.monotonic()
            r.require(remaining > 0, 'Worker readiness deadline exceeded')
            result = r.worker_probe(domain, 'verify', work, timeout=min(12, remaining))
            r.require(result['node'] == saved['node'], 'Celery node changed')
            r.require(time.monotonic() <= deadline, 'Worker readiness deadline exceeded')
            break
        except (RuntimeError, ValueError, subprocess.TimeoutExpired):
            r.require(time.monotonic() < deadline, 'Worker readiness timed out; inspect stage')
            time.sleep(1)
    current = r.worker(domain)
    env = (Path('/proc') / str(current['pid']) / 'environ').read_bytes().split(b'\0')
    wanted = config['prefix'] + 'CODEX_AUTH_BROKER_SOCKET=' + ('/run/hengxin-codex-auth/broker.sock' if rollback else str(r.RUNTIME / 'worker.sock'))
    r.require(wanted.encode() in env, 'Worker socket configuration mismatch')
    r.private(work / (domain + '-stage.json'), {'phase': 'rolled-back' if rollback else 'verified', **current})
    return 'WORKER_ROLLED_BACK' if rollback else 'WORKER_VERIFIED'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','test','start'] + [a+'-'+d for a in ('api','worker','rollback-api','rollback-worker') for d in r.DOMAINS])
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--test-python', type=Path, help='Isolated Linux venv with pytest; never install into live worker environments')
    args = parser.parse_args()
    r.require(os.geteuid() == 0, 'Root required')
    os.umask(0o077)
    args.work.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (args.work / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if args.action == 'prepare':
                result = prepare(args.work, args.source.resolve())
            elif args.action in ('test','start'):
                result = test(args.work, args.test_python) if args.action == 'test' else start(args.work)
            else:
                domain = args.action.rsplit('-',1)[1]
                function = switch_worker if 'worker' in args.action else switch_api
                result = function(args.work,domain,args.action.startswith('rollback'))
            print(result)
        except BaseException as error:
            r.private(args.work / 'FAILURE.json', {'action':args.action,'errorType':type(error).__name__,
                'recovery':'Inspect stage and RECOVERY.txt. No automatic rollback, credential restore, DB restore or forced task stop.'})
            raise


if __name__ == '__main__':
    main()
