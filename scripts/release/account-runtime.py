"""Bounded host operations and baseline checks; never print credentials or raw environments."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

DOMAINS = {
    'domestic': dict(container='hengxin-vps-staging-api-1', unit='hengxin-vps-codex-worker.service',
                     uid=1001, gid=1001, module='app.worker.celery_app', queue='celery', prefix=''),
    'overseas': dict(container='hengxin-overseas-api-1', unit='hengxin-overseas-worker.service',
                     uid=999, gid=987, module='app.overseas.execution.worker', queue='overseas.cli', prefix='OVERSEAS_'),
}
SERVICE = 'hengxin-codex-accounts.service'
RUNTIME = Path('/run/hengxin-codex-accounts')
PRIVATE = Path('/home/codex/account-management')
APP = Path('/opt/hengxin-smart-image')
API_FILES = {'app/main.py', 'app/overseas/main.py', 'app/core/config.py'} | {
    'app/account_management/' + n for n in ('client.py', 'router.py', 'schemas.py')}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def run(*args, timeout=45, **kwargs):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kwargs)
    require(result.returncode == 0, 'Host command failed: ' + str(args[0]) + '; inspect host privately')
    return result.stdout.strip()


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private(path, value):
    require(not path.is_symlink(), 'Linked evidence path')
    temporary = path.with_name(path.name + '.new')
    with temporary.open('x') as stream:
        stream.write(value if isinstance(value, str) else json.dumps(value, indent=2))
    temporary.chmod(0o600)
    os.replace(temporary, path)


def verify_package(source):
    manifest = json.loads((source / 'release.json').read_text())
    require(manifest['frontendVersion'] == '0.2.54' and manifest['apiUid'] == 10001, 'Unexpected manifest')
    for name, expected in manifest['files'].items():
        path = source / name
        require(path.resolve().is_relative_to(source.resolve()) and not path.is_symlink(), 'Unsafe package path')
        require(digest(path) == expected, 'Package checksum mismatch: ' + name)
    for domain in DOMAINS:
        require(set(manifest['apis'][domain]['files']) == API_FILES, 'Unexpected API files')
    return manifest


def inspect(domain):
    return json.loads(run('docker', 'inspect', DOMAINS[domain]['container']))[0]


def worker(domain):
    config = DOMAINS[domain]
    pid = int(run('systemctl', 'show', config['unit'], '-p', 'MainPID', '--value'))
    require(pid > 0, 'Worker not running')
    directory = Path('/proc') / str(pid)
    require(directory.stat().st_uid == config['uid'], 'Worker UID drift')
    return dict(pid=pid, cwd=os.readlink(directory / 'cwd'))


def topology():
    containers = {}
    for name in run('docker', 'ps', '-a', '--format', '{{.Names}}').splitlines():
        if name not in {d['container'] for d in DOMAINS.values()}:
            row = json.loads(run('docker', 'inspect', name))[0]
            containers[name] = [row['Id'], row['State']['Running']]
    excluded = {d['unit'] for d in DOMAINS.values()} | {SERVICE}
    units = run('systemctl', 'list-units', '--type=service', '--state=running', '--no-legend')
    services = {row.split()[0]: run('systemctl', 'show', row.split()[0], '-p', 'MainPID', '--value')
                for row in units.splitlines() if 'hengxin' in row and row.split()[0] not in excluded}
    return dict(containers=containers, services=services)


def compose_info(live):
    labels = live['Config']['Labels']
    data = dict(project=labels['com.docker.compose.project'], cwd=labels['com.docker.compose.project.working_dir'],
                paths=labels['com.docker.compose.project.config_files'].split(','),
                env=labels.get('com.docker.compose.project.environment_file'))
    files = data['paths'] + ([data['env']] if data['env'] else [data['cwd'] + '/.env'])
    require(all(Path(p).is_file() and p.startswith('/opt/') for p in files), 'Compose source missing')
    data['files'] = {p: digest(p) for p in files}
    return data


def compose(data, *args, overlay=None):
    command = ['docker', 'compose', '-p', data['project'], '--project-directory', data['cwd']]
    if data['env']:
        command += ['--env-file', data['env']]
    for path in data['paths'] + ([str(overlay)] if overlay else []):
        command += ['-f', path]
    # Only the original .env files may interpolate configuration.
    return run(*command, *args, cwd=data['cwd'], env={'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'}, timeout=120)


def check_live_config(live, config):
    declared = config['services']['api']
    env = dict(item.split('=', 1) for item in live['Config']['Env'])
    require(all(env.get(k) == str(v) for k,v in declared.get('environment', {}).items()), 'Live/Compose env drift')
    require(run('docker', 'image', 'inspect', '--format', '{{.Id}}', declared['image']) == live['Image'], 'Live image drift')
    require(declared.get('command', live['Config']['Cmd']) == live['Config']['Cmd'], 'Live command drift')
    mounts = {v['Destination']: v for v in live['Mounts']}
    require(len(mounts) == len(declared.get('volumes', [])), 'Live mount count drift')
    for v in declared.get('volumes', []):
        m = mounts[v['target']]
        require(m['RW'] == (not v.get('read_only', False)), 'Live mount mode drift')
        require(m['Source'] == v['source'] if v['type'] == 'bind'
                else m['Name'] == config['volumes'][v['source']]['name'], 'Live mount source drift')


def api_hashes(image):
    code = ('import hashlib,json,pathlib; print(json.dumps({n:hashlib.sha256(pathlib.Path("/app",n).read_bytes()).hexdigest() '
            'if pathlib.Path("/app",n).is_file() else None for n in ' + repr(sorted(API_FILES)) + '}))')
    return json.loads(run('docker', 'run', '--rm', '--network', 'none', '--read-only', '--entrypoint', 'python', image,
                         '-B', '-c', code))


def drop_path(domain):
    return Path('/etc/systemd/system') / (DOMAINS[domain]['unit'] + '.d') / 'zzzzzzzzzzzzz-account-management.conf'


def worker_probe(domain, mode, work, timeout=150):
    state = worker(domain)
    raw = (Path('/proc') / str(state['pid']) / 'environ').read_bytes()
    env = dict(x.decode().split('=',1) for x in raw.split(b'\0') if x)
    env['PYTHONPATH'] = state['cwd']
    return json.loads(run(state['cwd'] + '/.venv/bin/python', str(Path(__file__).with_name('account-worker.py')),
                         domain, mode, str(state['pid']), str(work), cwd=state['cwd'], env=env, timeout=timeout))


def service_unit(source):
    return ('[Unit]\nDescription=Hengxin isolated Codex account manager\nAfter=network-online.target\n'
            '[Service]\nType=simple\nUser=codex\nGroup=hengxin-codex-auth\n'
            'WorkingDirectory=' + str(source / 'daemon') + '\nRuntimeDirectory=hengxin-codex-accounts\n'
            'RuntimeDirectoryMode=0750\nRuntimeDirectoryPreserve=yes\nUMask=0077\n'
            'ExecStart=/usr/bin/python3 -B -m app.account_management.service --root ' + str(PRIVATE) +
            ' --legacy-source /home/codex/auth/auth.json --runtime ' + str(RUNTIME) +
            ' --binary /opt/hengxin-runtime/codex-0.162.1/codex --bwrap /opt/hengxin-runtime/bwrap --api-uid 10001\n'
            'NoNewPrivileges=yes\nRestart=on-failure\nRestartSec=5\n[Install]\nWantedBy=multi-user.target\n')
