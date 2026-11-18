"""Offline runtime transaction tests. Production service and /proc calls are simulated."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codex_runtime_config as config
import codex_runtime_maintenance as runtime
import scope_catalog
import scope_snapshot
import scopes


def contents(path, source):
    if path in config.ENVS:
        prefix = config.key(config.ENVS[path])
        return (f'{prefix}BINARY="{config.binary(source)}"\n'
                f'{prefix}VERSION="{source}"\nOTHER="unchanged"\n').encode()
    if path in (config.UNIT, config.TEMPLATE):
        return f'ExecStart="/python" "account" "--binary" "{config.binary(source)}"\n'.encode()
    return json.dumps({s: {config.key(s)+'BINARY': config.binary(source),
                           config.key(s)+'VERSION': source, 'data': 'unrelated'} for s in config.ENVS.values()}).encode()


@pytest.mark.parametrize('path', config.FILES)
def test_only_pinned_references_change(path):
    before, after = (contents(path, v) for v in (config.OLD, config.NEW))
    assert config.substitute(path, before, config.OLD, config.NEW) == after
    assert config.substitute(path, after, config.NEW, config.OLD) == before
    with pytest.raises(RuntimeError):
        config.substitute(path, before+b'other=0.167.1', config.OLD, config.NEW)


@pytest.mark.parametrize('path', config.FILES)
def test_same_ref_count_wrong_field_refused(path):
    before = contents(path, config.OLD).replace(b'CODEX_VERSION', b'OTHER_VERSION').replace(b'--binary', b'--other')
    with pytest.raises(RuntimeError):
        config.substitute(path, before, config.OLD, config.NEW)


@pytest.fixture
def world(monkeypatch, tmp_path):
    m = runtime
    u = m.u
    mon = monkeypatch.setattr
    paths = {p: tmp_path / ('config-' + str(i)) for i, p in enumerate(config.FILES)}
    original_envs = config.ENVS
    mon(config, 'ENVS', {paths[p]: n for p, n in original_envs.items()})
    for name in ('UNIT', 'TEMPLATE', 'INVENTORY'):
        mon(config, name, paths[getattr(config, name)])
    mon(config, 'FILES', tuple(paths.values()))
    for p in config.FILES:
        p.write_bytes(contents(p, config.OLD))
    store = m.release.retention_store(tmp_path/'state')
    tool = m.release.Release(store)
    mon(u, 'safe', lambda *a, **k: None)
    mon(u, 'write', lambda p, data, mode: p.write_bytes(data))
    mon(m.gates, 'sync_directory', lambda p: None)
    mon(m, 'check_overrides', lambda: None)
    queues = {name: ['q-'+name] for name in m.WORKERS}
    services = {name: 'active' for name in m.SERVICES}
    w = SimpleNamespace(version=config.OLD, gate=True, queues=queues.copy(), services=services,
                        inject='', stops=0, wrong_snapshot=False)
    mon(m.gates, 'gate_state', lambda *a: w.gate)
    mon(m.gates, 'set_gate', lambda u,n,opened: setattr(w,'gate',opened))
    mon(u, 'contexts', lambda: {s: {'user': 0, 'env': {}, 'python': '/isolated/venv/bin/python',
                                    'cwd': '/separate/backend'} for s in m.SERVICES})
    mon(m, 'runtime', lambda ctx,v: m.snapshot.same({'version':v},{'version':w.version}))
    mon(u, 'prop', lambda n,k: {'ActiveState':w.services[n], 'MainPID':'0',
                                'ControlGroup':'/system.slice/'+n+'.service'}[k])
    socket = {'socket': [0,1001,0o660]}
    w.sockets = copy.deepcopy(socket)
    mon(m, 'socket_state', lambda: copy.deepcopy(w.sockets))
    mon(m, 'restore_sockets', lambda expected: setattr(w,'sockets',copy.deepcopy(expected)))
    def gate(s):
        w.sockets['socket'][2] = 0
        if w.inject == 'account':
            raise RuntimeError('active login')
    def drain(ctx, paused, names):
        for name in names:
            w.queues[name] = []
            if w.inject == 'drain':
                raise RuntimeError('outstanding jobs')
    def control(name, action, ctx, deadline):
        if action == 'resume':
            w.queues[name] = list(queues[name])
        return {'queues': list(w.queues[name])}
    mon(u, 'drain', drain)
    mon(u, 'control', control)
    def stop(state):
        assert not w.gate
        assert all(not w.queues[n] for n in m.WORKERS if w.services[n]=='active')
        assert w.sockets['socket'][2] == 0 or w.services[m.ACCOUNT] == 'inactive'
        w.stops += 1
        w.services.update(dict.fromkeys(m.SERVICES, 'inactive'))
    def start(state):
        w.version = config.NEW if config.NEW.encode() in config.UNIT.read_bytes() else config.OLD
        w.services.update(dict.fromkeys(m.SERVICES,'active'))
        w.queues = copy.deepcopy(queues)
        w.sockets = copy.deepcopy(socket)
        if w.inject == 'partial' and w.version == config.NEW:
            w.services[m.WORKERS[1]] = 'inactive'
            w.queues[m.WORKERS[1]] = []
            raise RuntimeError('partial native startup')
    mon(m, 'graceful_stop', stop)
    mon(m, 'start', start)
    def capture(*args, **kwargs):
        imgs = {n: 'image-'+n for n in (*u.APPS,*scopes.UI.values())}
        return dict(groups={s:{'backend':s+'-backend','frontend':s+'-frontend'} for s in scopes.GROUPS},
                    configs={str(p):m.snapshot.sha(p.read_bytes()) for p in (*config.ENVS,config.UNIT)},
                    native={n:'identity-'+n for n in u.NATIVE}, schema={s:'schema-'+s for s in scopes.GROUPS},
                    data={'db':'changed' if w.inject=='snapshot' and w.version==config.NEW else 'original'},
                    images=imgs, binaries={n:{config.binary(w.version):config.DIGEST[w.version], '/bwrap':'original'} for n in m.WORKERS})
    mon(tool,'capture',capture)
    current = capture()
    data = dict(version=2,current=current,pending=None, previous=None, source_history=['previous'],
                groups={s:dict(current=scope_snapshot.group(current,s), previous={'release':'old-'+s},
                               previous_work='history-'+s) for s in scopes.GROUPS}, retention={'version':2})
    scope_catalog.seal(data)
    tool.save(data)
    switch = m.Switch(tool, SimpleNamespace(gate_account=gate),'codex-runtime-1.json')
    w.switch, w.tool, w.initial, w.store, w.orig_queues = switch,tool,data,store,queues
    return w


def test_forward_and_pinned_reverse_preserve_all_release_history(world):
    w = world
    for old, new in [(config.OLD,config.NEW),(config.NEW,config.OLD)]:
        state = w.switch.prepare(old,new)
        w.switch.run(state)
        updated = w.tool.load()
        scope_catalog.check(updated)
        assert w.gate and w.version == new and w.queues == w.orig_queues
        assert updated['groups']['shared'] == w.initial['groups']['shared']
        for s in scopes.GROUPS:
            assert updated['groups'][s]['previous'] == w.initial['groups'][s]['previous']
        assert updated['source_history'] == w.initial['source_history']
    assert w.tool.load() == w.initial


@pytest.mark.parametrize(('inject','stops'), [('drain',0),('account',0),('partial',2),('snapshot',2)])
def test_failures_restore_consumers_configs_and_ledger(world, inject, stops):
    w = world
    state = w.switch.prepare(config.OLD,config.NEW)
    w.inject = inject
    with pytest.raises(RuntimeError):
        w.switch.run(state)
    assert w.stops == stops and w.gate and w.version == config.OLD
    assert w.tool.load() == w.initial and w.queues == w.orig_queues
    assert runtime.load_marker(runtime.u,w.store)['phase'] == 'rolled-back'
    assert all(p.read_bytes() == contents(p,config.OLD) for p in config.FILES)


def test_crash_after_atomic_ledger_commit_finishes_without_rolling_back(world, monkeypatch):
    w = world
    state = w.switch.prepare(config.OLD,config.NEW)
    original = w.tool.save
    def interrupted(updated):
        original(updated)
        raise OSError('after atomic replace')
    monkeypatch.setattr(w.tool, 'save', interrupted)
    w.switch.run(state)
    assert w.gate and w.version == config.NEW and w.stops == 1
    assert runtime.load_marker(runtime.u,w.store)['phase'] == 'complete'


def test_guard_blocks_unfinished_work(world):
    w = world
    w.switch.marker('running')
    with pytest.raises(RuntimeError,match='pending Codex'):
        runtime.guard(runtime.u,w.store)
    w.switch.marker('rolled-back')
    runtime.guard(runtime.u,w.store)

def test_saved_cgroup_with_child_blocks_switch_even_if_systemd_forgot_it(tmp_path, monkeypatch):
    m = runtime
    groups = {name: '/system.slice/' + name + '.service' for name in m.SERVICES}
    mon = monkeypatch.setattr
    mon(m.u, 'SYSTEMD', tmp_path/'systemd')
    mon(m.credentials, 'CGROUP_ROOT', tmp_path/'cgroups')
    mon(m.u, 'safe', lambda *a,**k: None)
    mon(m.u, 'prop', lambda n,k: {'SendSIGKILL':'no','Restart':'no','ActiveState':'inactive',
                                    'MainPID':'0','ControlGroup':''}[k])
    mon(m.u, 'run', lambda *a,**k: None)
    mon(m.u, 'write', lambda path, data, **k: path.write_bytes(data))
    for name in m.SERVICES:
        m.override(name).parent.mkdir(parents=True)
    folder = m.credentials.CGROUP_ROOT/groups[m.AUX[0]].lstrip('/')
    (folder/'child').mkdir(parents=True)
    (folder/'cgroup.procs').write_text('')
    (folder/'child/cgroup.procs').write_text('123\n')
    with pytest.raises(RuntimeError,match='live processes'):
        m.graceful_stop({'cgroups':groups})


def test_start_waits_for_new_endpoints_before_workers(monkeypatch):
    m = runtime
    events = []
    expected = {'account':[1001,1001,0o660]}
    observations = iter([FileNotFoundError(), {'account':[1001,1001,0]}, expected])
    def sockets():
        events.append('probe')
        obs = next(observations)
        if isinstance(obs, Exception):
            raise obs
        return obs
    monkeypatch.setattr(m,'socket_state',sockets)
    monkeypatch.setattr(m.credentials,'prepare_accounts',lambda u,s,uid: events.append('cleanup'))
    monkeypatch.setattr(m,'override',lambda n: SimpleNamespace(exists=lambda:False))
    monkeypatch.setattr(m.u,'run',lambda cmd,**k:events.append(tuple(cmd)))
    m.start({'sockets':expected,'account_uid':1001})
    assert events == ['cleanup', ('systemctl','daemon-reload'),('systemctl','start',m.ACCOUNT,*m.AUX),
                      'probe','probe','probe',('systemctl','start',*m.WORKERS)]
