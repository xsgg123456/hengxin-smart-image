"""Repeatable .245 source switching using the proven migration primitives.

Caller owns the host/root check and process lock for the entire command.
Private transaction files contain service environments; never print their data.
"""
import importlib.util
import json
from pathlib import Path
import time

_spec = importlib.util.spec_from_file_location(
    'intranet_unify_release', Path(__file__).resolve().parents[3] / 'hengxin-smart-image/scripts/migration245/unify_release.py')
u = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(u)


def configure(release: Path, work: Path):
    u.RELEASE, u.WORK, u.REUSABLE = Path(release), Path(work), True


def _save(name, value, exclusive=False):
    u.write(u.WORK / name, (json.dumps(value, indent=2) + '\n').encode(), exclusive=exclusive)


def _read(name):
    path = u.WORK / name
    u.safe(path)
    return json.loads(path.read_bytes())


def _dropin(name):
    return u.SYSTEMD / (name + '.service.d') / u.DROPIN


def _inventory():
    paths = set(u.config_paths())
    for name in u.NATIVE:
        directory = u.SYSTEMD / (name + '.service.d')
        if directory.exists():
            u.safe(directory)
            for path in directory.iterdir():
                u.safe(path)
                if path.name != '91-unify-stop.conf':
                    paths.add(path)
    return sorted(str(p) for p in paths if p.name != '91-unify-stop.conf')


def prepare():
    u.prepare()
    baseline = _read('prepared.json')
    baseline.update(engine=1, release=str(u.RELEASE), inventory=_inventory())
    if set(baseline['inventory']) != {r['path'] for r in baseline['configs']}:
        raise RuntimeError('Unloaded configuration requires manual review')
    _save('prepared.json', baseline)
    return 'prepared'


def _check(baseline, recovering=False, state=None):
    if baseline.get('engine') != 1 or baseline.get('release') != str(u.RELEASE):
        raise RuntimeError('Unrecognized transaction/release')
    if u.data_identity() != baseline['data_containers']:
        raise RuntimeError('Data container identity drift')
    originals = {r['path']: r for r in baseline['configs']}
    candidates = {str(u.COMPOSE): baseline['candidate']}
    candidates.update({str(_dropin(n)): baseline['dropins'][n] for n in u.NATIVE})
    expected_inventory = set(baseline['inventory'])
    actual_inventory = set(_inventory())
    additions = actual_inventory - expected_inventory
    if expected_inventory - actual_inventory or additions - (set(candidates) if recovering else set()):
        raise RuntimeError('Configuration inventory drift')
    for item in baseline['configs']:
        backup = u.WORK / item['backup']
        u.safe(backup)
        if u.digest(backup.read_bytes()) != item['sha256']:
            raise RuntimeError('Configuration backup drift')
    for filename, expected in [('compose.candidate.json', baseline['candidate']),
                               *((n + '.conf', baseline['dropins'][n]) for n in u.NATIVE)]:
        path = u.WORK / filename
        u.safe(path)
        if u.digest(path.read_bytes()) != expected:
            raise RuntimeError('Candidate configuration drift')
    for name in set(originals) | set(candidates):
        path = Path(name)
        original = originals.get(name)
        allowed = {original['sha256']} if original else set()
        if recovering and name in candidates:
            allowed.add(candidates[name])
        if path.exists():
            u.safe(path)
            if u.digest(path.read_bytes()) not in allowed:
                raise RuntimeError('Configuration drift')
        elif original:
            raise RuntimeError('Configuration disappeared')
    for name in u.NATIVE:
        stop = _dropin(name).with_name('91-unify-stop.conf')
        if stop.exists():
            u.safe(stop)
            if not recovering or state['phase'] not in ('stopping', 'switching', 'starting', 'recovering') or stop.read_bytes() != u.STOP_OVERRIDE:
                raise RuntimeError('Concurrent maintenance drop-in')
    if not recovering and u.validate_release() != baseline['release_manifest']:
        raise RuntimeError('Release differs from prepared candidate')


class _JournalList(list):
    def __init__(self, state, key):
        self.state, self.key = state, key
        values = state[key]
        super().__init__([(Path(p), i, m) for p, i, m in values] if key == 'sockets' else values)

    def append(self, value):
        super().append(value)
        self.state[self.key] = [(str(p), i, m) for p, i, m in self] if self.key == 'sockets' else list(self)
        _save('started.json', self.state)


def _phase(state, phase):
    state['phase'] = phase
    _save('started.json', state)


def _restore_sockets(state):
    for name, inode, mode in state['sockets']:
        path = Path(name)
        if path.exists() and path.stat().st_ino == inode:
            path.chmod(mode)


def _load_state(baseline):
    state = _read('started.json')
    if state['prepared'] != u.digest((u.WORK / 'prepared.json').read_bytes()):
        raise RuntimeError('Prepared transaction drift')
    return state


def apply():
    baseline = _read('prepared.json')
    if (u.WORK / 'rolled-back.json').exists():
        raise RuntimeError('Rolled back transaction requires a new prepare')
    if (u.WORK / 'started.json').exists():
        state = _load_state(baseline)
        if state.get('recovering'):
            raise RuntimeError('Interrupted recovery requires recover')
        if (u.WORK / 'applied.json').exists():
            _check(baseline, recovering=True, state=state)
            if u.validate_release() != baseline['release_manifest']:
                raise RuntimeError('Applied release drift')
            for path, expected in [(u.COMPOSE, baseline['candidate']),
                                   *((_dropin(n), baseline['dropins'][n]) for n in u.NATIVE)]:
                if u.digest(path.read_bytes()) != expected:
                    raise RuntimeError('Applied configuration drift')
            return 'applied'
        raise RuntimeError('Existing transaction requires recover')
    _check(baseline)
    ctx = u.contexts()
    if {n: {k: v for k, v in c.items() if k != 'env'} for n, c in ctx.items()} != baseline['native']:
        raise RuntimeError('Native execution context drift')
    state = dict(prepared=u.digest((u.WORK / 'prepared.json').read_bytes()),
                 phase='ingress', ctx=ctx, paused=[], sockets=[])
    _save('started.json', state, exclusive=True)
    paused, sockets = _JournalList(state, 'paused'), _JournalList(state, 'sockets')
    try:
        u.app_command('stop', u.ENTRIES)
        u.drain(ctx, paused)
        u.gate_accounts(sockets)
        for name in u.NATIVE:
            _dropin(name).parent.mkdir(mode=0o755, exist_ok=True)
        _check(baseline)
        _phase(state, 'stopping')
        u.stop_apps()
        _check(baseline, recovering=True, state=state)
        if u.validate_release() != baseline['release_manifest']:
            raise RuntimeError('Release drift during drain')
        _phase(state, 'switching')
        for name in u.NATIVE:
            u.write(_dropin(name), (u.WORK / (name + '.conf')).read_bytes(), mode=0o644)
        u.write(u.COMPOSE, (u.WORK / 'compose.candidate.json').read_bytes())
        _phase(state, 'starting')
        u.start_apps(ctx)
        if u.validate_release() != baseline['release_manifest']:
            raise RuntimeError('Release drift after start')
        _check(baseline, recovering=True, state=state)
        _restore_sockets(state)
        _save('applied.json', {'manifest': baseline['release_manifest']}, exclusive=True)
        return 'applied'
    except BaseException:
        try:
            recover()
        except BaseException:
            raise RuntimeError('RECOVERY_UNCONFIRMED: inspect private transaction') from None
        raise


def _quiesce(state):
    ctx = state['ctx']
    live = []
    for name in u.WORKERS[:2]:
        if u.prop(name, 'ActiveState') == 'active':
            live.append(name)
        elif u.prop(name, 'MainPID') != '0':
            raise RuntimeError('Partial native startup is still executing')
    image = json.loads(u.run(['docker', 'inspect', 'hengxin-lan-' + u.WORKERS[2]]))[0]
    if image['State']['Running']:
        live.append(u.WORKERS[2])
    u.drain(ctx, _JournalList(state, 'paused'), live)
    credentials = ('hengxin-codex-accounts', 'hengxin-codex-auth')
    if all(u.prop(n, 'ActiveState') == 'active' for n in credentials):
        u.gate_accounts(_JournalList(state, 'sockets'))
    elif any(u.prop(n, 'MainPID') != '0' for n in credentials):
        raise RuntimeError('Partial credential startup; preserving processes')


def recover():
    baseline = _read('prepared.json')
    if not (u.WORK / 'started.json').exists():
        raise RuntimeError('No started transaction to recover')
    state = _load_state(baseline)
    if (u.WORK / 'rolled-back.json').exists():
        _check(baseline, recovering=True, state=state)
        originals = {r['path']: r['sha256'] for r in baseline['configs']}
        for path in [u.COMPOSE, *(_dropin(n) for n in u.NATIVE)]:
            if (u.digest(path.read_bytes()) if path.exists() else None) != originals.get(str(path)):
                raise RuntimeError('Restored configuration drift')
        return 'rolled-back'
    _check(baseline, recovering=True, state=state)
    state['recovering'] = True
    _save('started.json', state)
    u.app_command('stop', u.ENTRIES)
    try:
        if state['phase'] == 'ingress':
            _restore_sockets(state)
            for name in state['paused']:
                u.control(name, 'resume', state['ctx'], time.monotonic() + 30)
            u.app_command('up', u.ENTRIES)
            u.health(state['ctx'], frontend=True)
        else:
            _quiesce(state)
            _phase(state, 'recovering')
            u.remove_stop_overrides()
            u.stop_apps()
            _check(baseline, recovering=True, state=state)
            originals = {r['path']: r for r in baseline['configs']}
            for path in [u.COMPOSE, *(_dropin(n) for n in u.NATIVE)]:
                if str(path) in originals:
                    record = originals[str(path)]
                    u.write(path, (u.WORK / record['backup']).read_bytes(), record['mode'])
                else:
                    path.unlink(missing_ok=True)
            u.start_apps(state['ctx'])
            _restore_sockets(state)
        if u.data_identity() != baseline['data_containers']:
            raise RuntimeError('Data container identity changed during recovery')
        _save('rolled-back.json', {'restored': baseline['release_manifest']}, exclusive=True)
        return 'rolled-back'
    except BaseException:
        u.app_command('stop', u.ENTRIES)
        raise
