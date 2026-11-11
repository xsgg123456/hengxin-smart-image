"""Scoped process adapters for the existing engine, without another transaction loop."""
import json
import time
import urllib.request

import scopes


class Actions:
    def __init__(self, u, scope, mode, original, all_native, backend):
        self.u, self.scope, self.mode = u, scope, mode
        self.original, self.all_native, self.backend = original, all_native, backend
        self.workers = scopes.WORKERS[scope] if mode == 'full' else ()

    def shared_idle(self):
        """Read-only refusal: never pause business queues to upgrade shared services."""
        u = self.u
        business = {n: m for n, m in self.all_native.items() if n not in scopes.NATIVE['shared']}
        with scopes.replace(u, NATIVE=business):
            ctx = self.original['contexts']()
        deadline = time.monotonic() + 30
        for name in u.WORKERS:
            state = u.control(name, 'inspect', ctx, deadline)
            if any(state[k] for k in ('active', 'reserved', 'scheduled', 'database', 'broker')):
                raise RuntimeError('Shared release requires both business queues idle')

    def drain(self, ctx, paused, live=None):
        if self.mode == 'frontend':
            return
        if self.scope == 'shared':
            self.shared_idle()
            return
        self.original['drain'](ctx, paused, self.workers if live is None else live)

    def gate_accounts(self, sockets):
        if self.scope == 'shared' and self.mode == 'full':
            self.shared_idle()
            self.original['gate_accounts'](sockets)
            # Recheck after closing the credential sockets, before any stop.
            self.shared_idle()

    def quiesce(self, state):
        u = self.u
        live = []
        for name in self.workers:
            if name in u.NATIVE:
                if u.prop(name, 'ActiveState') == 'active':
                    live.append(name)
                elif u.prop(name, 'MainPID') != '0':
                    raise RuntimeError('Partial native startup is still executing')
            else:
                info = json.loads(u.run(['docker', 'inspect', 'hengxin-lan-' + name]))[0]
                if info['State']['Running']:
                    live.append(name)
        import engine
        self.drain(state['ctx'], engine._JournalList(state, 'paused'), live)
        if self.scope == 'shared' and self.mode == 'full':
            if all(u.prop(n, 'ActiveState') == 'active' for n in u.NATIVE):
                self.gate_accounts(engine._JournalList(state, 'sockets'))
            elif any(u.prop(n, 'MainPID') != '0' for n in u.NATIVE):
                raise RuntimeError('Partial credential startup; preserving processes')

    def stop_apps(self):
        u = self.u
        # Preserve the proven graceful native stop primitive. Its final compose
        # action may be empty for shared/frontend, which our app adapter handles.
        if u.NATIVE:
            self.original['stop_apps']()
        else:
            self.app_command('stop', tuple(n for n in u.APPS if n not in u.ENTRIES))

    def app_command(self, action, names, candidate=False):
        if names:
            return self.original['app_command'](action, names, candidate=candidate)

    def start_apps(self, ctx):
        u = self.u
        if u.NATIVE:
            self.original['remove_stop_overrides']()
            u.run(['systemctl', 'start', *u.NATIVE], timeout=180)
        backend = tuple(n for n in u.APPS if n != scopes.UI[self.scope])
        self.app_command('up', backend)
        if backend:
            self.health(ctx)
        self.app_command('up', (scopes.UI[self.scope],))
        self.health(ctx, frontend=True)

    def remove_stop_overrides(self):
        if self.u.NATIVE:
            self.original['remove_stop_overrides']()

    def probe_candidate(self, ctx, config):
        u = self.u
        u.compose('config', '--quiet', config=config)
        for name, module in u.PYTHON_SERVICES.items():
            u.compose('run', '--rm', '--no-deps', '--pull', 'never', '--entrypoint', 'python', name,
                      '-B', '-c', 'import importlib; importlib.import_module(' + repr(module) + ')', config=config)
        for name, module in u.NATIVE.items():
            u.native_run(ctx[name], code='import importlib; importlib.import_module(' + repr(module) + ')',
                         cwd=str(self.backend / 'backend'))
        for name in self.workers:
            if name in u.NATIVE:
                u.native_run(ctx[name], module='app.execution.runtime_check', cwd=str(self.backend / 'backend'))

    def health(self, ctx, frontend=False):
        u = self.u
        deadline = time.monotonic() + 150
        while True:
            try:
                if any(u.prop(n, 'ActiveState') != 'active' for n in u.NATIVE):
                    raise RuntimeError('Native service not active')
                for name, info in u.containers().items():
                    if name == scopes.UI[self.scope] and not frontend:
                        continue
                    if not info['State']['Running'] or info['State'].get('Health', {}).get('Status', 'healthy') != 'healthy':
                        raise RuntimeError('Application container not healthy')
                if self.mode == 'full':
                    port, path = scopes.READY[self.scope]
                    self._http(f'http://127.0.0.1:{port}{path}')
                for name in self.workers:
                    if u.control(name, 'inspect', ctx, deadline)['queues'] != [scopes.QUEUES[name]]:
                        raise RuntimeError('Consumer queue not restored')
                if frontend:
                    self._http(f'http://192.168.1.245:8080/{self.scope}/')
                return
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Application health deadline exceeded') from None
                time.sleep(2)

    @staticmethod
    def _http(url):
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status != 200:
                raise RuntimeError('HTTP readiness failed')
