"""Bounded, secret-safe host primitives for the dual-domain authentication patch."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

WORK = Path('/opt/hengxin-releases/codex-auth-20261019')
SOCKET = '/run/hengxin-codex-auth/broker.sock'
GROUP = 'hengxin-codex-auth'
BROKER = 'hengxin-codex-auth.service'
SYSTEMD = Path('/etc/systemd/system')
DOMAINS = {
    'domestic': dict(unit='hengxin-vps-codex-worker.service', uid=1001, gid=1001,
        target='/opt/hengxin-native-releases/domestic-codex-auth-20261019/backend',
        module='app.worker.celery_app', queue='celery', prefix=''),
    'overseas': dict(unit='hengxin-overseas-worker.service', uid=999, gid=987,
        target='/opt/hengxin-overseas-releases/overseas-codex-auth-20261019/backend',
        module='app.overseas.execution.worker', queue='overseas.cli', prefix='OVERSEAS_'),
}
ALLOWED = frozenset({
    'app/core/config.py', 'app/execution/workspace.py',
    'app/execution/managed_credentials.py', 'app/execution/managed_credentials_files.py',
    'app/execution/credential_broker.py', 'app/execution/credential_broker_client.py',
    'app/execution/credential_identity.py', 'app/execution/credential_errors.py',
    'app/modules/api_image_edits/conversation_runner.py',
    'app/modules/api_image_edits/conversation_errors.py',
    'app/overseas/execution/runner.py', 'app/overseas/execution/events.py',
    'app/overseas/studio/execution.py', 'app/overseas/studio/events.py',
})


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(*args, timeout=30, **kwargs):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kwargs)
        require(result.returncode == 0, 'Host command failed; inspect private host diagnostics')
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError('Host command timed out; inspect current stage') from None


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private(path, value):
    path = Path(path)
    require(not path.is_symlink(), 'Refuse linked evidence path')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as out:
        out.write(value if isinstance(value, str) else json.dumps(value, indent=2))
    path.chmod(0o600)


def live(domain):
    config = DOMAINS[domain]
    pid = int(run('systemctl', 'show', config['unit'], '-p', 'MainPID', '--value'))
    require(pid > 0, 'Worker is not running')
    cwd = Path(os.readlink(f'/proc/{pid}/cwd'))
    require(cwd == Path(run('systemctl', 'show', config['unit'], '-p', 'WorkingDirectory', '--value')),
            'Configured and actual worker directories differ')
    require(Path(f'/proc/{pid}').stat().st_uid == config['uid'], 'Unexpected worker UID')
    raw = Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
    env = {os.fsdecode(k): os.fsdecode(v) for k, v in (p.split(b'=', 1) for p in raw if p)}
    env['PYTHONPATH'] = str(cwd)
    return cwd, env, pid


def unrelated():
    excluded = {v['unit'] for v in DOMAINS.values()} | {BROKER}
    units = run('systemctl', 'list-units', '--type=service', '--state=running', '--no-legend')
    names = sorted(line.split()[0] for line in units.splitlines()
                   if 'hengxin' in line and line.split()[0] not in excluded)
    return dict(containers=sorted(run('docker', 'ps', '-a', '--no-trunc', '--format',
                                     '{{.Names}} {{.ID}} {{.Status}}').splitlines()),
        services={name: [run('systemctl', 'show', name, '-p', key, '--value')
                        for key in ('MainPID', 'WorkingDirectory')] for name in names})


def topology():
    value = unrelated()
    # Human-friendly uptime strings change even when containers remain untouched.
    value['containers'] = sorted(' '.join(line.split()[:2]) for line in value['containers'])
    return value


def tree(root):
    return {str(p.relative_to(root)).replace('\\', '/'): digest(p)
            for p in sorted((Path(root) / 'app').rglob('*.py')) if p.is_file()}


def patch(work, domain):
    data = json.loads((work / 'patch.json').read_text())
    require(set(data) == {'domains'} and set(data['domains']) == set(DOMAINS), 'Unexpected manifest domains')
    files = data['domains'][domain]['files']
    require(files and set(files) <= ALLOWED, 'Patch contains files outside reviewed allowlist')
    for name, entry in files.items():
        require(set(entry) == {'baseline', 'sha256'}, 'Unexpected file manifest fields')
        for key, value in entry.items():
            require(value is None and key == 'baseline' or isinstance(value, str)
                    and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'Invalid patch hash')
        source = work / 'src' / domain / name
        require(source.is_file() and not source.is_symlink() and digest(source) == entry['sha256'], 'Patch checksum mismatch')
    return files


def baseline(root, files):
    for name, entry in files.items():
        path = root / name
        require(not path.is_symlink(), 'Linked source baseline refused')
        actual = digest(path) if path.is_file() else None
        require(actual == entry['baseline'], 'Live source baseline differs: ' + name)


def drop_path(domain):
    return SYSTEMD / (DOMAINS[domain]['unit'] + '.d') / 'zzzz-codex-auth-20261019.conf'


def dropin(domain, node):
    require(re.fullmatch(r'[A-Za-z0-9_.@-]+', node) is not None, 'Unsafe Celery node identifier')
    config = DOMAINS[domain]
    root = config['target']
    queue = '' if domain == 'domestic' else ' --queues=overseas.cli'
    return ('[Service]\nWorkingDirectory=' + root + '\nExecStart=\nExecStart=' + root +
        '/.venv/bin/python ' + root + '/.venv/bin/celery -A ' + config['module'] +
        ':celery_app worker --pool=prefork --concurrency=5 --loglevel=INFO --hostname=' + node + queue +
        '\nSupplementaryGroups=' + GROUP + '\nEnvironment=' + config['prefix'] +
        'CODEX_AUTH_BROKER_SOCKET=' + SOCKET + '\n')


def broker_unit():
    root = DOMAINS['domestic']['target']
    return ('[Unit]\nDescription=Hengxin Codex access credential broker\nAfter=network-online.target\n'
        '[Service]\nType=simple\nUser=codex\nGroup=' + GROUP + '\nWorkingDirectory=' + root +
        '\nRuntimeDirectory=hengxin-codex-auth\nRuntimeDirectoryMode=0750\nUMask=0077\nExecStart=' + root +
        '/.venv/bin/python -m app.execution.credential_broker --source /home/codex/auth/auth.json --socket ' +
        SOCKET + ' --allowed-uid 1001 --allowed-uid 999\nNoNewPrivileges=yes\n'
        'Restart=on-failure\nRestartSec=5\n[Install]\nWantedBy=multi-user.target\n')


def worker_probe(domain, mode, work, timeout=120):
    cwd, env, pid = live(domain)
    config = DOMAINS[domain]
    output = run(str(cwd / '.venv/bin/python'), str(Path(__file__).with_name('codex_auth_worker.py')),
                 domain, mode, str(pid), str(work), cwd=cwd, env=env, timeout=timeout)
    return json.loads(output)


def probe_access(domain):
    config = DOMAINS[domain]
    group = run('getent', 'group', GROUP).split(':')[2]
    code = ('from app.execution.credential_broker_client import request_credentials; '
            'a=request_credentials(' + repr(SOCKET) + ',600); '
            'assert a["tokens"]["access_token"] and not a["tokens"]["refresh_token"]; print("ACCESS_ONLY_OK")')
    root = config['target']
    result = run('setpriv', '--reuid=' + str(config['uid']), '--regid=' + str(config['gid']),
        '--groups=' + group, root + '/.venv/bin/python', '-c', code,
        cwd=root, env={'PATH': '/usr/bin:/bin', 'PYTHONPATH': root}, timeout=90)
    require(result == 'ACCESS_ONLY_OK', 'UID access credential probe failed')
