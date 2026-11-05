"""Restore original API and native source without rewinding production data."""
import json
from pathlib import Path


def settled(r):
    for unit in r.UNITS:
        r.require(r.run('systemctl','show',unit,'-p','ActiveState','--value') in ('active','inactive'),
                  'Native stop still pending; retain protection')
        r.require(r.run('systemctl','show',unit,'-p','Job','--value') in ('','0'),
                  'Native job still pending; retain protection')


def worker_idle(r, node):
    status = r.worker('status', node)
    r.require(status['node'] == node, 'Worker node changed')
    result = r.worker('paused' if status['paused'] else 'idle', node)
    r.require(result['node'] == node, 'Worker node changed')
    return status


def resume_native(work, r, data, node):
    settled(r)
    if (work/'NATIVE_STOP_STARTED').exists():
        r.helper('sku-native').start(work, data, recovery=True)
    else:
        r.worker('resume', node)


def stop_native(work, r, data):
    native = r.helper('sku-native')
    settled(r)
    recovery_state = r.helper('studio-batch-recovery-state')
    recovery_state.begin(work,data,r,native)
    if all(native.pid(unit) == 0 for unit in r.UNITS):
        native.stopped()
        return
    node = json.loads((work/'gate.json').read_text())['node']
    if native.pid(r.UNITS[0]) > 0 and not worker_idle(r, node)['paused']:
        r.require(r.worker('pause')['node'] == node, 'Worker node changed')
    recovery_state.stop(work,data,r,native)


def recover(work, r, state, imports_idle, before_switch):
    data, _ = state(work, tested=True, release=True)
    r.require((work/'API_SWITCH_STARTED').exists() != before_switch, 'Wrong recovery phase')
    node = json.loads((work/'GATE_STARTED').read_text())['node']
    # Pause may have succeeded before gate.json was persisted.
    if not (work/'gate.json').exists():
        r.private(work/'gate.json', {'node':node, 'manifest':data['manifest'], 'phase':'recovering'})
    r.require(json.loads((work/'gate.json').read_text())['node'] == node, 'Gate node drift')
    settled(r)
    live = r.inspect()
    r.require(live['Image'] in (data['image'], data['oldImage']), 'Unrelated API image')
    if before_switch:
        r.require(live['Id'] == data['oldId'], 'Original API identity changed')
    if live['State']['Running']:
        imports_idle()
        worker_idle(r, node)
        r.run('docker', 'stop', '--time', '-1', r.API, timeout=60)
    r.require(not r.inspect()['State']['Running'], 'API stop unconfirmed; retain protection')
    # A request may have raced the gate. Recover the current API to finish durable work.
    try:
        imports_idle()
        if r.helper('sku-native').pid(r.UNITS[0]) > 0:
            worker_idle(r, node)
    except BaseException:
        r.require(not (work/'NATIVE_RECOVERY.json').exists(), 'Native recovery in progress; retain API protection')
        r.require(not (work/'NATIVE_PATCH_STARTED').exists() or (work/'NATIVE_VERIFIED').exists(),
                  'Partial native patch; retain API protection')
        resume_native(work, r, data, node)
        r.run('docker', 'start', r.API)
        r.helper('skill-folders-gateway').refresh(r, data)
        raise
    if (work/'NATIVE_PATCH_STARTED').exists() or (work/'NATIVE_RECOVERY.json').exists():
        stop_native(work, r, data)
        r.helper('studio-batch-native').restore(work, data)
    else:
        resume_native(work, r, data, node)
    r.helper('studio-batch-native').verify_baseline(data)
    r.require(r.hashes(data['oldImage']) == {n:v['baseline'] for n,v in data['patch'].items()},
              'Old API source drift')
    if before_switch:
        r.run('docker', 'start', r.API)
    else:
        r.a.compose(data['compose'], 'up', '-d', '--no-deps', '--no-build', 'api')
    old = r.inspect()
    r.require(old['Image'] == data['oldImage'] and old['State']['Running'], 'Old API not restored')
    r.a.check_live_config(old, json.loads(r.a.compose(data['compose'], 'config', '--format', 'json')))
    r.require(r.environment_hash(old['Config']['Env']) == data['environment']['api'], 'API environment drift')
    if (work/'frontend-backup/COMPLETE.json').exists():
        r.helper('sku-frontend').rollback(r.a.APP, work/'frontend-backup')
    r.worker_probe('overseas', 'verify', work)
    r.helper('skill-folders-gateway').refresh(r, data)
    r.require(r.b.tree(Path('/var/lib/hengxin-overseas/local-skills')) == data['protected']['skills'],
              'Skill bytes drift')
    r.private(work/('RECOVERED_BEFORE_SWITCH' if before_switch else 'ROLLED_BACK'),
              {'manifest':data['manifest'], 'image':data['oldImage'], 'nativeRestored':True})
    return 'ORIGINAL_API_NATIVE_FRONTEND_RESTORED_DATABASE_NOT_REWOUND'
