"""Read production metadata to a private stdout pipe; never run on the target."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from datetime import datetime, timezone

PROJECTS = {'hengxin-vps-staging', 'hengxin-overseas', 'hengxin-identity'}
CODE_ROOTS = {
    '/opt/hengxin-native-releases/domestic-record-filters-20261022-2f08f8f/backend',
    '/opt/hengxin-overseas-releases/overseas-20261024-b6289eb/backend',
    '/opt/hengxin-account-releases/account-management-20261026-ce4baf4/daemon',
    '/opt/hengxin-native-releases/domestic-codex-auth-20261019/backend',
}
EXCLUDED = {'.venv', '__pycache__', '.pytest_cache', '.git', 'node_modules'}
ROOT_DATA = {'execution', 'sessions', 'grants', 'logs', '.codex', 'runtime'}
UNITS = (
    'hengxin-codex-accounts', 'hengxin-codex-auth', 'hengxin-domestic-deletions',
    'hengxin-retention', 'hengxin-vps-codex-worker',
    'hengxin-overseas-worker', 'hengxin-overseas-outbox',
)


def run(*args):
    return subprocess.check_output(args, timeout=45)


def file_hashes(roots):
    hashes = {}
    for root in sorted(roots):
        for directory, dirs, names in os.walk(root, followlinks=False):
            excluded = EXCLUDED | (ROOT_DATA if Path(directory) == Path(root) else set())
            dirs[:] = [d for d in dirs if d not in excluded
                       and not (Path(directory) / d).is_symlink()]
            for name in sorted(names):
                p = Path(directory) / name
                if p.is_symlink() or not p.is_file():
                    continue
                hashes[str(p)] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                                  'size': p.stat().st_size, 'mode': p.stat().st_mode & 0o777}
    return hashes


def collect():
    if socket.gethostname() != 'racknerd-058889d':
        raise RuntimeError('source host mismatch')
    names = run('docker', 'ps', '--format', '{{.Names}}').decode().splitlines()
    containers = json.loads(run('docker', 'inspect', *names))
    containers = [c for c in containers if
                  c['Config']['Labels'].get('com.docker.compose.project') in PROJECTS]
    if len(containers) != 16:
        raise RuntimeError('source service inventory changed')
    units = []
    config_paths = set()
    roots = set()
    for name in UNITS:
        raw = run('systemctl', 'show', name + '.service',
                  '-p', 'MainPID,User,Group,WorkingDirectory,ExecStart,FragmentPath,'
                        'DropInPaths,EnvironmentFiles,ActiveState,UnitFileState').decode()
        props = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
        pid = int(props['MainPID'])
        if pid <= 0 or props['ActiveState'] != 'active':
            raise RuntimeError('source unit not active: ' + name)
        proc = Path('/proc') / str(pid)
        env = {}
        for entry in (proc / 'environ').read_bytes().split(b'\0'):
            if b'=' in entry:
                key, value = entry.split(b'=', 1)
                env[key.decode()] = value.decode()
        cmd = [x.decode() for x in (proc / 'cmdline').read_bytes().split(b'\0') if x]
        cwd = os.readlink(proc / 'cwd')
        if cwd not in CODE_ROOTS or Path(cwd).resolve() != Path(cwd):
            raise RuntimeError('unexpected source code root')
        roots.add(cwd)
        config_paths.add(props['FragmentPath'])
        config_paths.update(props['DropInPaths'].split())
        units.append({'name': name, 'properties': props, 'environment': env,
                      'argv': cmd, 'cwd': cwd})
    config_paths.update({
        '/opt/hengxin-smart-image/infra/nginx.vps.conf',
        '/etc/apparmor.d/hengxin-codex-userns',
        '/etc/apparmor.d/hengxin-codex-0.156.1',
        '/etc/apparmor.d/hengxin-task-isolation',
    })
    config = {p: Path(p).read_text() for p in sorted(config_paths) if p}
    hashes = file_hashes(roots)
    release = Path('/opt/hengxin-overseas-releases/'
                   'overseas-light-20261107-d7c21a1/src/release.json')
    return {'host': socket.gethostname(), 'observed_at': datetime.now(timezone.utc).isoformat(),
            'containers': containers, 'units': units, 'config_files': config,
            'native_hashes': hashes, 'frontend_release': json.loads(release.read_text())}


if __name__ == '__main__':
    json.dump(collect(), sys.stdout, ensure_ascii=False)
