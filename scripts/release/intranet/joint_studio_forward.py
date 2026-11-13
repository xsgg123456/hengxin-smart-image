"""Resume a schema-committed joint switch; never replay the old deployment."""
import json

import engine
import joint_studio_engine
import scopes


def stop_existing(u):
    """Stop only the known application services after the existing drain checks."""
    for name in u.NATIVE:
        path = engine._dropin(name).with_name('91-unify-stop.conf')
        path.parent.mkdir(mode=0o755, exist_ok=True)
        if path.exists():
            u.safe(path)
            if path.read_bytes() != u.STOP_OVERRIDE:
                raise RuntimeError('Unknown stop override')
        else:
            u.write(path, u.STOP_OVERRIDE, mode=0o644, exclusive=True)
    u.run(['systemctl', 'daemon-reload'])
    u.run(['systemctl', 'stop', *u.NATIVE], timeout=110)
    if any(u.prop(name, 'MainPID') != '0' for name in u.NATIVE):
        raise RuntimeError('Native process remains active')
    services = json.loads(u.COMPOSE.read_bytes())['services']
    names = tuple(name for name in u.APPS if name not in u.ENTRIES)
    if scopes.DOMESTIC_PUBLISHER in services:
        names = tuple(dict.fromkeys((*names, scopes.DOMESTIC_PUBLISHER)))
    with scopes.replace(u, APPS=tuple(dict.fromkeys((*u.APPS, scopes.DOMESTIC_PUBLISHER)))):
        u.app_command('stop', names)


def resume(expected_overseas):
    u = engine.u
    baseline = engine._read('prepared.json')
    state = engine._load_state(baseline)
    if state['phase'] not in ('stopping', 'switching', 'starting', 'recovering'):
        raise RuntimeError('Unrecognized forward recovery phase')
    engine._check(baseline, recovering=True, state=state)
    joint_studio_engine.check_migration(u, baseline, expected_overseas)
    if (u.WORK / 'applied.json').exists():
        return engine.apply()
    u.app_command('stop', u.ENTRIES)
    try:
        engine._quiesce(state)
        engine._phase(state, 'recovering')
        stop_existing(u)
        engine._check(baseline, recovering=True, state=state)
        if u.validate_release() != baseline['release_manifest']:
            raise RuntimeError('Candidate drift during forward recovery')
        engine._phase(state, 'switching')
        for name in u.NATIVE:
            u.write(engine._dropin(name), (u.WORK / (name + '.conf')).read_bytes(), mode=0o644)
        u.write(u.COMPOSE, (u.WORK / 'compose.candidate.json').read_bytes())
        engine._phase(state, 'starting')
        u.start_apps(state['ctx'])
        engine._check(baseline, recovering=True, state=state)
        joint_studio_engine.check_migration(u, baseline, expected_overseas)
        if u.validate_release() != baseline['release_manifest']:
            raise RuntimeError('Candidate drift after forward recovery')
        engine._restore_sockets(state)
        engine._save('applied.json', {'manifest': baseline['release_manifest']}, exclusive=True)
        return 'applied'
    except BaseException:
        u.app_command('stop', u.ENTRIES)
        raise
