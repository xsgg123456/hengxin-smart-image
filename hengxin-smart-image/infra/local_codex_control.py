"""Explicit Windows/WSL local switch. Errors never echo subprocess output/secrets."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from dotenv import dotenv_values

import local_codex_keeper as keeper_control
from local_codex_keeper import Refused, require

INFRA = Path(__file__).resolve().parent
SERVICE = 'hengxin-local-codex.service'
UNIT_PATH = '/etc/systemd/system/' + SERVICE
TERMINAL_SQL = "('succeeded','partial','failed','cancelled')"
# All jobs are checked, including installs: stopping a consumer must not interrupt them.
IDLE_SQL = ("SELECT (SELECT count(*) FROM job_records WHERE status IS NULL OR status NOT IN "
            + TERMINAL_SQL + ") + (SELECT count(*) FROM execution_rounds WHERE status IS NULL OR status NOT IN "
            + TERMINAL_SQL + ");")


def configuration(project, env_file, local_file):
    require(bool(re.fullmatch(r'hx-local-[a-z0-9][a-z0-9_-]{0,40}', project))
            and 'prod' not in project, 'Project must be an explicit hx-local-* non-production project')
    paths = [Path(p).resolve(strict=True) for p in (env_file, local_file)]
    require(all(p.parent == INFRA and p.name.startswith('.env') and 'prod' not in p.name.lower()
                for p in paths), 'Configuration files must be non-production .env files inside this infra')
    require(paths[0] != paths[1], 'Docker and local configuration must be separate files')
    base, local = [dict(dotenv_values(p, interpolate=False)) for p in paths]
    require(base.get('APP_ENV') in ('test', 'development'), 'APP_ENV must explicitly be test or development')
    require(all(isinstance(v, str) for v in [*base.values(), *local.values()]), 'Configuration contains unset values')
    require(all(k.startswith('LOCAL_CODEX_') for k in local), 'Local configuration may only contain LOCAL_CODEX_* keys')
    require(local.get('LOCAL_CODEX_DISTRO') == 'Ubuntu-24.04'
            and local.get('LOCAL_CODEX_USER') == 'hengxin', 'Only Ubuntu-24.04 / non-root hengxin is supported')
    for key in ('PYTHON', 'BINARY', 'AUTH_FILE', 'BWRAP', 'EXECUTION_ROOT', 'SKILL_ROOT'):
        value = local.get('LOCAL_CODEX_' + key, '')
        require(value.startswith('/') and not any(ord(c) < 32 for c in value), 'Invalid absolute WSL runtime path')
    require(bool(re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', local.get('LOCAL_CODEX_NODE', ''))), 'Invalid worker node name')
    for key, default in [('POSTGRES_PORT', '55433'), ('MINIO_PORT', '59002'), ('API_PORT', '8008'),
                         ('MINIO_CONSOLE_PORT', '59003'), ('LOCAL_CODEX_REDIS_PORT', '')]:
        value = (local if key.startswith('LOCAL_') else base).get(key, default)
        require(value.isascii() and value.isdigit() and 1 <= int(value) <= 65535, 'Invalid local port')
    require(all(base.get(k) for k in ('POSTGRES_PASSWORD', 'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY')), 'Missing Docker credentials')
    return paths, base, local


def unit_quote(value):
    require(not any(ord(c) < 32 for c in value), 'Control character in unit path')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


class Controller:
    def __init__(self, project, env_file, local_file):
        self.paths, self.base, self.local = configuration(project, env_file, local_file)
        self.project = project
        compose_keys = set(re.findall(r'\$\{([A-Z_][A-Z0-9_]*)',
                           (INFRA / 'compose.yaml').read_text(encoding='utf-8') +
                           (INFRA / 'compose.local-codex.yaml').read_text(encoding='utf-8')))
        self.env = {k: v for k, v in os.environ.items()
                    if k not in compose_keys and not k.startswith(('DOCKER_', 'COMPOSE_', 'LOCAL_CODEX_'))}
        self.env.update(self.base | self.local)  # Explicit files win over ambient Compose interpolation.
        self.docker = ['docker', '--context', 'desktop-linux']
        self.compose = self.docker + ['compose', '--project-name', project, '--project-directory', str(INFRA),
                                     '--env-file', str(self.paths[0]), '--env-file', str(self.paths[1]),
                                     '-f', str(INFRA / 'compose.yaml')]
        self.containers = []

    def run(self, argv, *, input=None, allowed=(0,)):
        try:
            result = subprocess.run(argv, input=input, capture_output=True, text=True, encoding='utf-8',
                                    errors='replace', env=self.env, timeout=180, shell=False)
        except (OSError, subprocess.TimeoutExpired):
            raise Refused('Command unavailable or timed out; no automatic rollback; inspect local service state') from None
        require(result.returncode in allowed, 'Command failed; output withheld to protect credentials')
        return result.stdout.strip()

    def wsl(self, *args, root=False, **kwargs):
        return self.run(['wsl.exe', '--distribution', self.local['LOCAL_CODEX_DISTRO'], '--user',
                         'root' if root else self.local['LOCAL_CODEX_USER'], '--exec', *args], **kwargs)

    def compose_up(self, real, *services):
        extra = ['-f', str(INFRA / 'compose.local-codex.yaml')] if real else []
        self.run(self.compose + extra + ['up', '-d', '--no-deps', '--no-build', '--wait',
                                       '--wait-timeout', '90', *services])

    def inspect(self):
        endpoint = json.loads(self.run(self.docker + ['context', 'inspect', 'desktop-linux']))[0]['Endpoints']['docker']['Host']
        require(endpoint in ('npipe:////./pipe/dockerDesktopLinuxEngine', 'npipe:////./pipe/docker_engine'),
                'Docker context must use the local Windows named pipe')
        ids = self.run(self.docker + ['ps', '-aq', '--filter', 'label=com.docker.compose.project=' + self.project]).split()
        require(bool(ids), 'Project is not initialized; this controller does not bootstrap databases')
        self.containers = json.loads(self.run(self.docker + ['inspect', *ids]))
        for c in self.containers:
            labels = c['Config']['Labels']
            require(labels.get('com.docker.compose.project') == self.project
                    and Path(labels.get('com.docker.compose.project.working_dir', '')).resolve() == INFRA
                    and Path(labels.get('com.docker.compose.project.config_files', '').split(',')[0]).resolve() == INFRA / 'compose.yaml',
                    'Container does not belong to this infra Compose project')
            values = dict(s.split('=', 1) for s in c['Config'].get('Env', []) if '=' in s)
            if labels.get('com.docker.compose.service') in ('api', 'worker', 'outbox'):
                require(values.get('APP_ENV') in ('test', 'development'), 'Production container refused')
            if labels.get('com.docker.compose.service') == 'postgres':
                require(values.get('POSTGRES_PASSWORD') == self.base['POSTGRES_PASSWORD'], 'Database configuration does not match project')
        require(len(self.ids('postgres')) == 1, 'Exactly one running project database is required')
        self.published_port('postgres', '5432/tcp', self.base.get('POSTGRES_PORT', '55433'))
        self.published_port('minio', '9000/tcp', self.base.get('MINIO_PORT', '59002'))

    def published_port(self, service, target, expected):
        matches = [c for c in self.containers if c['Id'] in self.ids(service)]
        require(len(matches) == 1, 'Exactly one running project ' + service + ' is required')
        bindings = matches[0].get('NetworkSettings', {}).get('Ports', {}).get(target)
        require(bindings == [{'HostIp': '127.0.0.1', 'HostPort': str(expected)}],
                'Published loopback port does not match project ' + service + ' configuration')

    def ids(self, service):
        return [c['Id'] for c in self.containers if c['Config']['Labels'].get('com.docker.compose.service') == service
                and c['State']['Running']]

    def idle(self):
        result = self.run(self.docker + ['exec', '-i', self.ids('postgres')[0], 'psql', '-X', '-U', 'hengxin',
                                       '-d', 'hengxin', '-v', 'ON_ERROR_STOP=1', '-At'], input=IDLE_SQL)
        require(result == '0', 'Switch refused: non-terminal jobs/rounds exist (including queued/uncertain), or database check failed')

    def prepare_unit(self, install=False):
        paths = [self.wsl('wslpath', '-a', '-u', str(p)) for p in
                 (INFRA / 'local_codex_worker.py', *self.paths)]
        self.worker_paths = paths
        argv = [self.local['LOCAL_CODEX_PYTHON'], paths[0], 'serve', '--env-file', paths[1], '--local-file', paths[2]]
        unit = (f'# hx-local-control project={self.project}\n[Unit]\nDescription=Hengxin local Codex worker\n'
                '[Service]\nType=exec\nUser=hengxin\nKillMode=control-group\nRestart=no\n'
                'TimeoutStopSec=60\nStandardOutput=null\nStandardError=null\nUMask=0077\n'
                'ExecStart=:' + ' '.join(map(unit_quote, argv)) + '\n')
        # Exact legacy unit already established by the integration owner. Never overwrite it.
        legacy = ("[Unit]\nDescription=Hengxin local Codex development worker\nAfter=network-online.target\n"
                  "[Service]\nType=simple\nUser=hengxin\nWorkingDirectory=" + paths[0].rsplit('/', 2)[0] + '/backend\n'
                  'ExecStart=' + ' '.join(argv) + '\nRestart=on-failure\nRestartSec=5\nKillMode=control-group\n'
                  'TimeoutStopSec=15\nUMask=0077\n[Install]\nWantedBy=multi-user.target')
        if (self.project != 'hx-local-test' or self.paths != [INFRA / '.env', INFRA / '.env.local-codex']
                or not all(re.fullmatch(r'[a-zA-Z0-9_./:-]+', a) for a in argv)):
            legacy = ''
        # Exclusive creation; never overwrite an existing or foreign service, or follow a symlink.
        script = ("import pathlib,sys,json; p=pathlib.Path(sys.argv[1]); expected,legacy=json.load(sys.stdin); "
                  "exists=p.exists(); assert not p.is_symlink(); "
                  "assert not exists or p.read_text().strip() in (expected.strip(),legacy); "
                  "p.open('x').write(expected) if not exists and sys.argv[2]=='install' else None")
        self.wsl('/usr/bin/python3', '-c', script, UNIT_PATH, 'install' if install else 'check', root=True,
                 input=json.dumps([unit, legacy]))
        require(not self.wsl('systemctl', 'show', SERVICE, '--property=DropInPaths', '--value', root=True),
                'Service drop-ins are not supported; review the dedicated unit')
        require(self.wsl('systemctl', 'show', SERVICE, '--property=FragmentPath', '--value', root=True)
                in ('', UNIT_PATH), 'Dedicated service is loaded from an unexpected location')
        if install:
            self.wsl('systemctl', 'daemon-reload', root=True)

    def keeper(self, stop=False):
        keeper_control.manage_keeper(self.project, INFRA, self.run, stop=stop)

    def preflight(self):
        self.prepare_unit()
        require(self.wsl('id', '-u') not in ('', '0'), 'Worker must be non-root')
        self.wsl(self.local['LOCAL_CODEX_PYTHON'], self.worker_paths[0], 'check', '--env-file',
                 self.worker_paths[1], '--local-file', self.worker_paths[2])

    def worker_ready(self):
        self.wsl('systemctl', 'is-active', '--quiet', SERVICE, root=True)
        # Target the actual Celery node; a surviving systemd process alone is not readiness.
        code = ("import os,sys,socket,time; from pathlib import Path; "
                "sys.path.insert(0,str(Path(sys.argv[1]).parent)); from local_codex_worker import configuration; "
                "os.environ.update(configuration(sys.argv[2],sys.argv[3])); "
                "sys.path.insert(0,str(Path(sys.argv[1]).parents[1]/'backend')); "
                "from app.worker.celery_app import celery_app; "
                "node=os.environ['WORKER_NODE_NAME']+'@'+socket.gethostname()\n"
                "for attempt in range(8):\n"
                " if any(reply.get(node,{}).get('ok')=='pong' for reply in "
                "celery_app.control.ping(destination=[node],timeout=3)): break\n"
                " time.sleep(1)\n"
                "else: raise RuntimeError('Worker not ready')")
        self.wsl(self.local['LOCAL_CODEX_PYTHON'], '-c', code, *self.worker_paths)

    def stop_containers(self, services):
        ids = [cid for service in services for cid in self.ids(service)]
        if ids:
            # -1 drains in-flight HTTP/DB requests without a forced kill.
            self.run(self.docker + ['stop', '--timeout', '-1', *ids])

    def execute(self, action):
        self.inspect()
        self.prepare_unit()
        if action == 'status':
            state = self.wsl('systemctl', 'show', SERVICE, '--property=ActiveState', '--value', root=True)
            require(state in ('active', 'inactive', 'failed', 'activating', 'deactivating', ''), 'Unexpected service state')
            print(json.dumps({'project': self.project, 'wslWorker': state or 'not-found',
                              'runningServices': sorted({c['Config']['Labels']['com.docker.compose.service']
                                                        for c in self.containers if c['State']['Running']})}))
            return
        if action in ('start', 'check'):
            self.preflight()
        if action == 'check':
            self.idle()
            print('PASS local configuration, ownership, CLI sandbox/auth preflight and idle database; no model call')
            return
        if action == 'fixture':
            require(self.base.get('ENABLE_FIXTURE_EXECUTOR', '').lower() == 'true'
                    and self.base.get('ENABLE_CODEX_EXECUTOR', 'false').lower() == 'false',
                    'Fixture requires explicit fixture=true and codex=false in the base .env')
        self.idle()  # Refuse already-busy environments before touching services.
        if action == 'start':
            self.keeper()
        old_api = self.ids('api')
        self.stop_containers(['api'])
        try:
            self.idle()  # API fully exited: no in-flight request can enqueue after this check.
        except Refused:
            if old_api:
                self.run(self.docker + ['start', *old_api])
            raise
        try:
            self.stop_containers(['outbox', 'worker'])
            if action == 'start':
                self.prepare_unit(install=True)
                self.compose_up(True, 'redis')
                self.inspect()
                self.published_port('redis', '6379/tcp', self.local['LOCAL_CODEX_REDIS_PORT'])
                self.wsl('systemctl', 'restart', SERVICE, root=True)
                self.worker_ready()
                self.compose_up(True, 'outbox')
                self.compose_up(True, 'api')  # Open admission only after the consumer is ready.
            else:
                loaded = self.wsl('systemctl', 'show', SERVICE, '--property=LoadState', '--value', root=True)
                if loaded != 'not-found':
                    self.wsl('systemctl', 'stop', SERVICE, root=True)
                self.keeper(stop=True)
                if action == 'fixture':
                    self.compose_up(False, 'worker', 'outbox')
                    self.compose_up(False, 'api')
        except BaseException:
            # No automatic mode rollback after touching consumers. Fail closed, preserve all data.
            self.inspect()
            self.stop_containers(['api'])
            raise
        print('PASS ' + action + '; existing task records and data volumes retained')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'start', 'stop', 'fixture', 'status'])
    parser.add_argument('--project', default='hx-local-test')
    parser.add_argument('--env-file', default=str(INFRA / '.env'))
    parser.add_argument('--local-file', default=str(INFRA / '.env.local-codex'))
    args = parser.parse_args()
    handle = None
    try:
        require(sys.platform == 'win32', 'Use this controller on Windows')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateMutexW(None, False, 'Local\\hengxin-local-codex-control')
        require(handle and ctypes.get_last_error() != 183, 'Another local controller is active')
        Controller(args.project, args.env_file, args.local_file).execute(args.action)
        return 0
    except Refused as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print('Control failed; details withheld to protect credentials. API may remain stopped; inspect status.', file=sys.stderr)
        return 1
    finally:
        if handle:
            kernel.CloseHandle(handle)


if __name__ == '__main__':
    sys.exit(main())
