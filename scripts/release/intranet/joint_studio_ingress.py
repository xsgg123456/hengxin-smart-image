"""Keep the joint candidate private until runtime verification and ledger commit."""
from contextlib import contextmanager
import json
from pathlib import Path
import stat
import time
import urllib.request

import engine
import joint_studio_credentials as credentials
import joint_studio_forward as forward
import joint_studio_gate_wiring as gate_wiring
import joint_studio_paths as paths
import joint_studio_private_config as private_config
import scope_snapshot
import scopes
import snapshot


API = private_config.API
NGINX_TARGET = private_config.NGINX_TARGET
verify_nginx_dump = private_config.verify_nginx_dump


class PrivateIngress:
    def __init__(self, u, app_command, health, restore_sockets, start_apps=None, quiesce=None):
        self.u, self.original_app = u, app_command
        self.original_health, self.restore_sockets = health, restore_sockets
        self.original_start, self.original_quiesce = start_apps, quiesce or engine._quiesce
        self.original_frontend = scope_snapshot.verify_frontend
        self.paused = False

    def state(self):
        return engine._load_state(engine._read('prepared.json'))

    def stage_config(self):
        return private_config.stage_config(self.u)

    def web(self):
        rows = json.loads(self.u.run(['docker', 'inspect', 'hengxin-lan-domestic-web']))
        if len(rows) != 1:
            raise RuntimeError('Gateway identity is ambiguous')
        info = rows[0]
        labels = info['Config'].get('Labels') or {}
        if (info['Name'] != '/hengxin-lan-domestic-web'
                or labels.get('com.docker.compose.project') != 'hengxin-lan'
                or labels.get('com.docker.compose.service') != 'domestic-web'):
            raise RuntimeError('Gateway identity changed')
        return info

    def assert_private(self):
        info = self.web()
        host = info['HostConfig']
        ports = info['NetworkSettings'].get('Ports') or {}
        if (not info['State'].get('Running') or host.get('NetworkMode') == 'host'
                or any((host.get('PortBindings') or {}).values()) or any(ports.values())):
            raise RuntimeError('Candidate gateway has a published host port')
        mounts = [item for item in info['Mounts'] if item.get('Destination') == NGINX_TARGET]
        if (len(mounts) != 1 or mounts[0].get('Source') != str(self.u.WORK / 'nginx.private-gateway.conf')
                or mounts[0].get('RW') is not False):
            raise RuntimeError('Candidate gateway access guard differs')
        config = self.u.run(['docker', 'exec', 'hengxin-lan-domestic-web', 'nginx', '-T'])
        verify_nginx_dump(config)

    def assert_api(self, name, private):
        rows = json.loads(self.u.run(['docker', 'inspect', 'hengxin-lan-' + name]))
        if len(rows) != 1:
            raise RuntimeError('API identity is ambiguous: ' + name)
        info = rows[0]
        labels = info['Config'].get('Labels') or {}
        bindings = info['HostConfig'].get('PortBindings') or {}
        ports = info['NetworkSettings'].get('Ports') or {}
        command = info['Config'].get('Cmd') or []
        expected_host = '127.0.0.1' if private else '0.0.0.0'
        expected_ports = {'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': API[name][1]}]}
        if (info['Name'] != '/hengxin-lan-' + name or not info['State'].get('Running')
                or labels.get('com.docker.compose.project') != 'hengxin-lan'
                or labels.get('com.docker.compose.service') != name
                or info['HostConfig'].get('NetworkMode') == 'host'
                or command[:4] != ['uvicorn', API[name][0], '--host', expected_host]
                or (private and (any(bindings.values()) or any(ports.values())))
                or (not private and (bindings != expected_ports or ports != expected_ports))):
            raise RuntimeError('API listener isolation differs: ' + name)

    def assert_public(self):
        info = self.web()
        expected = {'80/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18080'}]}
        if (not info['State'].get('Running') or info['HostConfig'].get('NetworkMode') == 'host'
                or info['HostConfig'].get('PortBindings') != expected
                or info['NetworkSettings'].get('Ports') != expected):
            raise RuntimeError('Published gateway binding differs')

    def stage(self, names=('domestic-web',)):
        config = self.stage_config()
        self.u.compose('up', '-d', '--no-deps', '--pull', 'never', *names, config=config)
        for name in set(names) & set(API):
            self.assert_api(name, private=True)
        if 'domestic-web' in names:
            self.assert_private()

    def preflight(self, before):
        private_config.verify_source(self.u, before)
        config = self.stage_config()
        self.u.compose('config', '--quiet', config=config)
        dump = self.u.compose('run', '--rm', '--no-deps', '--pull', 'never', '--entrypoint', 'nginx',
                              'domestic-web', '-T', config=config)
        verify_nginx_dump(dump)

    def app_command(self, action, names, candidate=False):
        if action == 'up' and set(names) & set(self.u.ENTRIES) and not candidate:
            return self.stage(names)
        return self.original_app(action, names, candidate=candidate)

    def request(self, path):
        self.assert_private()
        return self.u.run(['docker', 'exec', 'hengxin-lan-domestic-web', 'curl',
                           '--fail', '--silent', '--show-error', '--max-time', '10',
                           'http://127.0.0.1' + path])

    def verify_frontend(self, scope, manifest):
        if scope not in scopes.GROUPS:
            raise RuntimeError('Invalid private frontend scope')
        content = self.request('/' + scope + '/').encode('utf-8')
        if snapshot.sha(content) != manifest['files']['frontend/index.html']:
            raise RuntimeError('Private frontend differs from release: ' + scope)

    def normalize(self, after, before):
        return private_config.normalize(self.u, after, before)

    def socket_modes(self, state, gated):
        records = state['sockets']
        for name in self.u.ACCOUNT_SOCKETS:
            path = Path(name)
            info = path.lstat()
            matches = [mode for item, inode, mode in records if item == name and inode == info.st_ino]
            if (not stat.S_ISSOCK(info.st_mode) or len(matches) != 1
                    or stat.S_IMODE(info.st_mode) != (0 if gated else matches[0])):
                raise RuntimeError('Credential socket gate changed')

    @contextmanager
    def bounded(self, deadline):
        original = self.u.run
        def run(args, **kwargs):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('Readiness deadline exceeded')
            kwargs['timeout'] = min(kwargs.get('timeout', 60), remaining)
            return original(args, **kwargs)
        with scopes.replace(self.u, run=run):
            yield

    def runtime_once(self, ctx, frontend):
        u = self.u
        self.require_closed()
        if any(u.prop(name, 'ActiveState') != 'active' for name in u.NATIVE):
            raise RuntimeError('Native service not active')
        for name, info in u.containers().items():
            if name == 'domestic-web' and not frontend:
                continue
            if not info['State']['Running'] or info['State'].get('Health', {}).get('Status', 'healthy') != 'healthy':
                raise RuntimeError('Application container not healthy')
        gate_wiring.verify(scope_snapshot.containers(u, domestic_publisher=True), u.contexts())
        code = ("import sys,urllib.request; "
                "opener=urllib.request.build_opener(urllib.request.ProxyHandler({})); "
                "r=opener.open('http://127.0.0.1:8000'+sys.argv[1],timeout=5); assert r.status==200")
        for name, (_, _, path) in API.items():
            self.assert_api(name, private=True)
            u.run(['docker', 'exec', 'hengxin-lan-' + name, 'python', '-B', '-c', code, path], timeout=10)
        self.socket_modes(self.state(), gated=True)
        if frontend:
            self.request('/')

    def health(self, ctx, frontend=False):
        deadline = time.monotonic() + 150
        with self.bounded(deadline):
            while True:
                try:
                    self.runtime_once(ctx, frontend)
                    return
                except Exception:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RuntimeError('Private runtime health deadline exceeded') from None
                    time.sleep(min(2, remaining))

    def start(self, start_apps, ctx):
        self.require_closed()
        self.paused = True
        def credentials_ready():
            credentials.gate_started(self.u, self.state())
            self.socket_modes(self.state(), gated=True)
        start_apps(ctx, after_credentials=credentials_ready,
                   before_credentials=lambda: credentials.prepare(self.u, self.state()))
        self.health(ctx, frontend=True)

    def require_closed(self):
        if paths.gate_state(self.u, 'workers') or paths.gate_state(self.u, 'ingress'):
            raise RuntimeError('Candidate release gates must remain closed')

    def seal(self):
        workers_open = paths.gate_state(self.u, 'workers')
        paths.set_gate(self.u, 'ingress', False)
        self.original_app('stop', self.u.ENTRIES)
        if workers_open and (self.u.WORK / 'started.json').exists():
            self.original_quiesce(self.state())
        # Keep the worker marker open until every process has stopped. A retry
        # after SIGKILL can then tell whether an additional drain is needed.
        forward.stop_existing(self.u)
        paths.set_gate(self.u, 'workers', False)
        self.paused = True

    def ensure_private(self):
        self.seal()
        if self.original_start is None:
            raise RuntimeError('Missing private startup routine')
        apps = tuple(dict.fromkeys((*self.u.APPS, scopes.DOMESTIC_PUBLISHER)))
        with scopes.replace(self.u, APPS=apps):
            self.start(self.original_start, self.state()['ctx'])

    @contextmanager
    def public_checks(self):
        with scopes.replace(self.u, health=self.pending_public_health), \
             scopes.replace(scope_snapshot, verify_frontend=self.original_frontend):
            yield

    def pending_public_health(self, ctx, frontend=False):
        self.require_closed()
        self.socket_modes(self.state(), gated=True)
        if any(self.u.prop(name, 'ActiveState') != 'active' for name in self.u.NATIVE):
            raise RuntimeError('Native service not active')
        for info in self.u.containers().values():
            if not info['State']['Running'] or info['State'].get('Health', {}).get('Status', 'healthy') != 'healthy':
                raise RuntimeError('Application container not healthy')
        gate_wiring.verify(scope_snapshot.containers(self.u, domestic_publisher=True), self.u.contexts())
        for name in API:
            self.assert_api(name, private=False)
        if frontend:
            self.assert_public()

    def open_public(self, expected):
        state = self.state()
        self.require_closed()
        self.socket_modes(state, gated=True)
        self.original_app('up', tuple(API))
        deadline = time.monotonic() + 150
        with self.bounded(deadline):
            while True:
                try:
                    for name, (_, port, path) in API.items():
                        self.assert_api(name, private=False)
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise RuntimeError('Published API readiness deadline exceeded')
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=min(5, remaining)) as response:
                            if response.status != 200:
                                raise RuntimeError('Published API readiness failed: ' + name)
                    break
                except Exception:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RuntimeError('Published API readiness deadline exceeded') from None
                    time.sleep(min(2, remaining))
        self.original_app('up', ('domestic-web',))
        self.assert_public()
        for _, _, path in API.values():
            with urllib.request.urlopen('http://192.168.1.245:8080' + path, timeout=5) as response:
                if response.status != 200:
                    raise RuntimeError('Published gateway API routing failed')
        with self.public_checks():
            actual = scope_snapshot.capture(self.u, runtime=True, domestic_publisher=True)
        snapshot.same(expected, actual)
        self.restore_sockets(state)
        self.socket_modes(state, gated=False)
        paths.set_gate(self.u, 'workers', True)
        self.original_health(self.u.contexts(), frontend=True)
        # This is the final action: abrupt termination before here leaves all
        # user-facing APIs closed, even if the publisher process disappears.
        paths.set_gate(self.u, 'ingress', True)
        self.paused = False
