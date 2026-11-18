"""Pinned joint Codex runtime maintenance for hengxin-ai-245."""
import argparse
import json
import os
from pathlib import Path
import socket
import stat
import time

import catalog
from codex_runtime_config import (ACCOUNT, AUX, NEW, OLD, SERVICES, WORKERS, binary, configs,
                                  expected_state, key, prerequisites, read_files, reseal)
from codex_runtime_marker import MARKER, guard, load_marker
import joint_studio_credentials as credentials
import engine
import joint_studio_paths as gates
import release
import scope_catalog
import snapshot

u = engine.u


def socket_state():
    result = {}
    for name in u.ACCOUNT_SOCKETS[:3]:
        info = Path(name).lstat()
        if not stat.S_ISSOCK(info.st_mode):
            raise RuntimeError('Unexpected account socket')
        result[name] = [info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)]
    return result


def restore_sockets(expected):
    actual = socket_state()
    for name, (uid, gid, mode) in expected.items():
        if actual[name][:2] != [uid, gid] or actual[name][2] not in (0, mode):
            raise RuntimeError('Account socket ownership/mode drift')
        if actual[name][2] != mode:
            Path(name).chmod(mode)
    if socket_state() != expected:
        raise RuntimeError('Account socket restoration failed')


def runtime(ctx, version):
    for name in (*WORKERS, *AUX):
        env, prefix = ctx[name]['env'], key(name)
        if (env.get(prefix+'BINARY'), env.get(prefix+'VERSION')) != (binary(version), version):
            raise RuntimeError('Running Codex differs: ' + name)
    pid = u.prop(ACCOUNT, 'MainPID')
    args = Path('/proc', pid, 'cmdline').read_bytes().decode().split('\0')
    if args.count('--binary') != 1 or args[args.index('--binary') + 1] != binary(version):
        raise RuntimeError('Running account binary differs')


def override(name):
    return u.SYSTEMD / (name + '.service.d') / '91-unify-stop.conf'


def check_overrides():
    for name in SERVICES:
        path = override(name)
        u.safe(path, missing=True)
        if path.exists():
            raise RuntimeError('Existing maintenance stop override')


def graceful_stop(state):
    for name in SERVICES:
        path = override(name)
        u.safe(path, missing=True)
        if path.exists():
            if path.read_bytes() != u.STOP_OVERRIDE:
                raise RuntimeError('Unexpected maintenance override')
        else:
            u.write(path, u.STOP_OVERRIDE, mode=0o644, exclusive=True)
    u.run(['systemctl', 'daemon-reload'])
    for name in SERVICES:
        if u.prop(name, 'SendSIGKILL') != 'no' or u.prop(name, 'Restart') != 'no':
            raise RuntimeError('Graceful stop protection unavailable')
    u.run(['systemctl', 'stop', *SERVICES], timeout=120)
    for name in SERVICES:
        credentials.stopped(u, name)
        # An inactive unit may already have cleared systemd's ControlGroup field.
        credentials.empty_group(u, state['cgroups'][name])


def wait_sockets(expected):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            if socket_state() == expected:
                return
        except FileNotFoundError:
            pass
        time.sleep(.1)
    raise RuntimeError('Account sockets did not become ready')


def start(state):
    credentials.prepare_accounts(u, state['sockets'], state['account_uid'])
    for name in SERVICES:
        path = override(name)
        if path.exists():
            u.safe(path)
            if path.read_bytes() != u.STOP_OVERRIDE:
                raise RuntimeError('Maintenance override drift')
            path.unlink()
    u.run(['systemctl', 'daemon-reload'])
    u.run(['systemctl', 'start', ACCOUNT, *AUX], timeout=120)
    wait_sockets(state['sockets'])
    u.run(['systemctl', 'start', *WORKERS], timeout=120)


def queues(ctx):
    deadline = time.monotonic() + 60
    return {n: sorted(u.control(n, 'inspect', ctx, deadline)['queues']) for n in WORKERS}


class Switch:
    def __init__(self, tool, helper, journal):
        self.tool, self.store, self.helper, self.journal = tool, tool.store, helper, journal

    def save(self, state, phase):
        state['phase'] = phase
        self.store.report(self.journal, state)

    def marker(self, phase):
        self.store.report(MARKER, dict(phase=phase, journal=self.journal))

    def prepare(self, source, target):
        data = self.tool.load()
        if data['version'] != 2 or data['pending'] or data.get('migration_pending'):
            raise RuntimeError('Clean v2 release ledger required')
        scope_catalog.check(data)
        snapshot.same(data['current'], self.tool.capture(data, runtime=True))
        if not all(gates.gate_state(u, name) for name in ('ingress', 'workers')):
            raise RuntimeError('Production maintenance gate already closed')
        check_overrides()
        ctx = u.contexts()
        runtime(ctx, source)
        records = read_files(source, target)
        expected = expected_state(data['current'], records, source, target)
        before_queues = queues(ctx)
        sockets = socket_state()
        account_uid = ctx[ACCOUNT]['user']
        if not all(before_queues.values()) or any(x[0] != account_uid or x[2] != 0o660 for x in sockets.values()):
            raise RuntimeError('Consumer or credential ingress already closed')
        cgroups = {n: u.prop(n, 'ControlGroup') for n in SERVICES}
        if any(not group.startswith('/') or '..' in Path(group).parts
               or Path(group).name != name + '.service' for name, group in cgroups.items()):
            raise RuntimeError('Native service cgroup identity differs')
        return dict(source=source, target=target, old_ledger=catalog.state_sha(data),
                    new_ledger=catalog.state_sha(reseal(data, expected)), files=records,
                    ctx={s: ctx[s] for s in WORKERS}, queues=before_queues, sockets=sockets,
                    cgroups=cgroups, account_uid=account_uid)

    def drain(self, state, names):
        # The established controller checks active/reserved/scheduled, SQL and broker.
        # It refuses when any queue survives pause. Restoration uses the observed baseline.
        u.drain(state['ctx'], [], tuple(names))

    def resume(self, state):
        deadline = time.monotonic() + 75
        # A freshly restarted systemd unit may precede its Celery control endpoint.
        for name in WORKERS:
            while time.monotonic() < deadline:
                try:
                    current = u.control(name, 'inspect', state['ctx'], deadline)['queues']
                    if sorted(current) == state['queues'][name]:
                        break
                    u.control(name, 'resume', state['ctx'], deadline)
                except RuntimeError:
                    pass
                time.sleep(min(1, max(0, deadline-time.monotonic())))
            else:
                raise RuntimeError('Consumer restoration unconfirmed: ' + name)

    def confirm(self, state, data, expected, version):
        configs(state, 'before' if version == state['source'] else 'after')
        ctx = u.contexts()
        runtime(ctx, version)
        snapshot.same(expected, self.tool.capture(data, runtime=True))
        if queues(ctx) != state['queues'] or socket_state() != state['sockets']:
            raise RuntimeError('Consumer or credential restoration unconfirmed')

    def run(self, state):
        self.save(state, 'gating')
        self.marker('running')
        try:
            gates.set_gate(u, 'ingress', False)
            self.drain(state, WORKERS)
            self.helper.gate_account([])
            configs(state, 'before')
            self.save(state, 'stopping')
            graceful_stop(state)
            configs(state, 'apply')
            start(state)
            restore_sockets(state['sockets'])
            data = self.tool.load()
            if catalog.state_sha(data) != state['old_ledger']:
                raise RuntimeError('Ledger changed during switch')
            expected = expected_state(data['current'], state['files'], state['source'], state['target'])
            self.confirm(state, data, expected, state['target'])
            updated = reseal(data, expected)
            if catalog.state_sha(updated) != state['new_ledger']:
                raise RuntimeError('Unexpected candidate ledger')
            self.save(state, 'committing')
            self.tool.save(updated)
            gates.set_gate(u, 'ingress', True)
            self.marker('complete')
        except BaseException:
            if self.recover(state) == 'complete':
                return
            raise

    def recover(self, state):
        data = self.tool.load()
        digest = catalog.state_sha(data)
        if digest == state['new_ledger'] and state['phase'] == 'committing':
            self.confirm(state, data, data['current'], state['target'])
            gates.set_gate(u, 'ingress', True)
            self.marker('complete')
            return 'complete'
        if digest != state['old_ledger']:
            raise RuntimeError('Ledger differs from recorded transaction')
        if state['phase'] != 'gating':
            # Restarted or partially started workers may have consumed new work.
            live = []
            for name in WORKERS:
                active = u.prop(name, 'ActiveState')
                if active == 'active':
                    live.append(name)
                elif active not in ('inactive', 'failed') or u.prop(name, 'MainPID') != '0':
                    raise RuntimeError('Native transition still executing: ' + name)
            self.drain(state, live)
            account = u.prop(ACCOUNT, 'ActiveState')
            if account == 'active':
                self.helper.gate_account([])
            elif account not in ('inactive', 'failed') or u.prop(ACCOUNT, 'MainPID') != '0':
                raise RuntimeError('Account service still transitioning')
            graceful_stop(state)
            configs(state, 'restore')
            start(state)
        restore_sockets(state['sockets'])
        self.resume(state)
        self.confirm(state, data, data['current'], state['source'])
        gates.set_gate(u, 'ingress', True)
        self.marker('rolled-back')
        return 'rolled-back'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'apply', 'rollback', 'recover'))
    action = parser.parse_args(argv).action
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('Only root on hengxin-ai-245 is permitted')
    root = Path('/var/lib/hengxin-release')
    u.safe(root)
    store = release.retention_store(root)
    with store.locked():
        helper = prerequisites(store)
        tool = release.Release(store)
        if action == 'recover':
            marker = load_marker(u, store)
            if not marker or marker['phase'] != 'running':
                raise RuntimeError('No incomplete runtime switch')
            journal = marker['journal']
            path = store.root / journal
            u.safe(path)
            Switch(tool, helper, journal).recover(json.loads(path.read_bytes()))
        else:
            guard(u, store)
            switch = Switch(tool, helper, 'codex-runtime-' + str(time.time_ns()) + '.json')
            source, target = (NEW, OLD) if action == 'rollback' else (OLD, NEW)
            state = switch.prepare(source, target)
            if action != 'check':
                switch.run(state)
    print('CODEX_RUNTIME_OK', action, flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('CODEX_RUNTIME_REFUSED: ' + (str(exc) if isinstance(exc, RuntimeError)
                                                       else type(exc).__name__)) from None
