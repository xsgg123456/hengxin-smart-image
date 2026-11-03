"""Minimal 0.2.61 switch: same schema, native bytes, Compose environment and Skill."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import time

spec = importlib.util.spec_from_file_location('polling_runtime', Path(__file__).with_name('polling-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.runtime
sku = r.helper('sku-deploy')


def state(work, tested=False, release=False):
    data, source = sku.state(work, tested)
    if release:
        r.require(r.verify_package(source)['mode'] == 'release', 'Candidate package is test-only; commit and repackage')
    r.require(r.sql(r.DB, 'SELECT version_num FROM overseas_alembic_version') == r.REVISION, 'Schema drift')
    return data, source


def prepare(work, source):
    r.require(not (work/'prepared.json').exists(), 'Inspect existing preparation')
    manifest, live = r.verify_package(source), r.inspect()
    r.require(live['State']['Running'] and live['Image'] == r.BASE_IMAGE, 'API baseline drift')
    r.require(r.hashes(live['Image']) == {n:v['baseline'] for n,v in manifest['api']['files'].items()}, 'Source drift')
    protected = r.b.snapshot()
    r.require(protected['frontendVersion'] == r.BASE_VERSION, 'Frontend baseline drift')
    r.require(r.sql(r.DB, 'SELECT version_num FROM overseas_alembic_version') == r.REVISION, 'Schema drift')
    data = dict(source=str(source), manifest=r.digest(source/'release.json'), oldId=live['Id'], oldImage=live['Image'],
        compose=r.a.compose_info(live), patch=manifest['api']['files'], native=manifest['native'], protected=protected,
        environment={'api':r.environment_hash(live['Config']['Env']),
                     'native':{u:r.native_environment(u) for u in r.UNITS}})
    # compose_info includes every actual config file, including the prior private secret overlay.
    r.helper('sku-native').preflight(data)
    before = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json'))
    r.a.check_live_config(live, before)
    context = work/'api-build'
    context.mkdir(mode=0o755)
    for name in sorted(r.FILES):
        target = context/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source/'api'/name, target)
    for path in context.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    tag = 'hengxin-smart-image-backend:'+manifest['release']
    r.require(not r.run('docker', 'images', '-q', tag), 'Release tag already exists')
    r.run('docker', 'tag', live['Image'], tag+'-base')
    (context/'Dockerfile').write_text('FROM '+tag+'-base\n'+''.join(
        'COPY '+n+' /app/'+n+'\n' for n in sorted(r.FILES)))
    r.run('docker', 'build', '--network=none', '--pull=false', '-t', tag, str(context), timeout=180)
    data['image'] = r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', tag)
    overlay = work/'api-overlay.json'
    r.private(overlay, {'services':{'api':{'image':data['image']}}})
    after = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json', overlay=overlay))
    before['services']['api']['image'] = data['image']
    r.require(after == before, 'Image overlay changes unrelated configuration')
    data['overlayHash'] = r.digest(overlay)
    r.unchanged(protected)
    r.private(work/'prepared.json', data)
    r.private(work/'RECOVERY.txt', 'No database migration or native source replacement is permitted. '
        'Before API_SWITCH_STARTED use recover-before-switch. After switching use rollback; '
        'never restore the dump over live data. Stop timeouts retain protection; never force-kill.\n')
    state(work)
    return 'PREPARED_NO_PRODUCTION_SWITCH'


def imports_idle():
    r.require(r.sql(r.DB, "SELECT count(*) FROM overseas_draft_imports WHERE state IN ('queued','running')") == '0',
              'Draft imports still active; recover original API if already stopped')


def gate(work):
    data, _ = state(work, tested=True, release=True)
    r.require(not (work/'GATE_STARTED').exists(), 'Inspect previous gate; do not overwrite recovery state')
    r.require(r.inspect()['Id'] == data['oldId'], 'API identity drift')
    node = r.worker('idle')['node']
    imports_idle()
    r.private(work/'GATE_STARTED', {'node':node, 'oldId':data['oldId']})
    # Docker never escalates to SIGKILL. HTTP requests finish during Uvicorn shutdown.
    # A newly queued import can race the precheck: postcheck aborts instead of claiming drain.
    r.run('docker', 'stop', '--time', '-1', r.API, timeout=60)
    r.require(not r.inspect()['State']['Running'], 'API stop not confirmed')
    imports_idle()
    r.worker('idle')
    r.require(r.worker('pause')['node'] == node, 'Worker changed')
    r.private(work/'gate.json', {'node':node, 'manifest':data['manifest'], 'phase':'api-stopped-consumer-paused'})
    r.helper('sku-native').stop(work, data)
    return 'API_AND_IMPORTS_DRAINED_NATIVE_STOPPED_WITHOUT_SOURCE_CHANGES'


def backup(work):
    data, _ = state(work, tested=True, release=True)
    return r.helper('polling-database').backup(work, data)


def api(work):
    data, _ = state(work, tested=True, release=True)
    database = r.helper('polling-database')
    database.closed_gate(work, data)
    database.backup_verified(work, data)
    r.require(not (work/'API_SWITCH_STARTED').exists(), 'Inspect previous switch attempt')
    r.helper('sku-native').start(work, data, recovery=True)
    r.private(work/'API_SWITCH_STARTED', {'manifest':data['manifest'], 'image':data['image']})
    r.a.compose(data['compose'], 'up', '-d', '--no-deps', '--no-build', 'api', overlay=work/'api-overlay.json')
    return verify(work)


def verify(work):
    data, _ = state(work, tested=True, release=True)
    live = r.inspect()
    r.require(live['Image'] == data['image'] and live['State']['Running'], 'New API not running')
    r.a.check_live_config(live, json.loads(r.a.compose(data['compose'], 'config', '--format', 'json',
        overlay=work/'api-overlay.json')))
    r.require(r.environment_hash(live['Config']['Env']) == data['environment']['api'], 'API environment changed')
    for unit in r.UNITS:
        r.require(r.native_environment(unit) == data['environment']['native'][unit], 'Native environment changed')
    r.worker_probe('overseas', 'verify', work)
    for port, path in ((18018, '/api/overseas/v1/health/ready'), (18080, '/api/v1/health/ready')):
        r.helper('image-cache-runtime').readiness('http://127.0.0.1:'+str(port)+path)
    r.private(work/'API_VERIFIED', {'manifest':data['manifest'], 'image':data['image'], 'id':live['Id']})
    return 'API_0.2.61_VERIFIED_SCHEMA_NATIVE_SKILL_CONFIGURATION_PRESERVED'


def frontend(work):
    data, source = state(work, tested=True, release=True)
    verify(work)
    return r.helper('sku-frontend').deploy(source, r.a.APP, work/'frontend-backup')


def resume(work):
    data, source = state(work, tested=True, release=True)
    verify(work)
    for name, digest in r.verify_package(source)['files'].items():
        if name.startswith('frontend/'):
            r.require(r.digest(r.a.APP/name) == digest, 'Installed frontend drift')
    r.private(work/'RESUMED', {'manifest':data['manifest'], 'image':data['image']})
    return 'RELEASE_VERIFIED'


def recover_before_switch(work):
    data, _ = state(work, tested=True, release=True)
    r.require(not (work/'API_SWITCH_STARTED').exists(), 'Use rollback after switch starts')
    live = r.inspect()
    r.require(live['Id'] == data['oldId'] and live['Image'] == data['oldImage'], 'Original API changed')
    r.require(not live['State']['Running'], 'API still stopping; wait for graceful shutdown')
    node = json.loads((work/'GATE_STARTED').read_text())['node']
    if (work/'NATIVE_STOP_STARTED').exists():
        r.helper('sku-native').start(work, data, recovery=True)
    else:
        r.worker('resume', node)
    r.run('docker', 'start', r.API)
    r.helper('image-cache-runtime').readiness('http://127.0.0.1:18018/api/overseas/v1/health/ready')
    r.private(work/'RECOVERED_BEFORE_SWITCH', {'oldId':data['oldId'], 'manifest':data['manifest']})
    return 'ORIGINAL_API_RECOVERED_PERSISTENT_IMPORTS_MAY_RESUME'


def rollback(work):
    data, _ = state(work, tested=True, release=True)
    r.require((work/'API_SWITCH_STARTED').exists(), 'Use recover-before-switch before switch')
    live = r.inspect()
    r.require(live['Image'] in (data['image'], data['oldImage']), 'Unrelated API image; stop and inspect')
    if live['State']['Running']:
        imports_idle()
        r.worker('idle')
        r.run('docker', 'stop', '--time', '-1', r.API, timeout=60)
    r.require(not r.inspect()['State']['Running'], 'API stop unconfirmed')
    # If a submission raced, restart the current image so durable work can finish; do not switch it.
    try:
        imports_idle()
        r.worker('idle')
    except BaseException:
        r.run('docker', 'start', r.API)
        raise
    r.require(r.hashes(data['oldImage']) == {n:v['baseline'] for n,v in data['patch'].items()}, 'Old image drift')
    r.a.compose(data['compose'], 'up', '-d', '--no-deps', '--no-build', 'api')
    old = r.inspect()
    r.require(old['Image'] == data['oldImage'] and old['State']['Running'], 'Old API not restored')
    r.a.check_live_config(old, json.loads(r.a.compose(data['compose'], 'config', '--format', 'json')))
    if (work/'frontend-backup/COMPLETE.json').exists():
        r.helper('sku-frontend').rollback(r.a.APP, work/'frontend-backup')
    r.helper('image-cache-runtime').readiness('http://127.0.0.1:18018/api/overseas/v1/health/ready')
    r.private(work/'ROLLED_BACK', {'manifest':data['manifest'], 'image':data['oldImage']})
    return 'ORIGINAL_API_FRONTEND_RESTORED_DATABASE_NOT_REWOUND'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'test', 'gate', 'backup', 'api', 'frontend',
                                          'verify', 'resume', 'recover-before-switch', 'rollback'))
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    r.require(os.geteuid() == 0, 'Root required')
    os.umask(0o077)
    args.work.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (args.work/'.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'prepare':
            r.require(args.source is not None, 'prepare requires --source')
            result = prepare(args.work, args.source.resolve())
        elif args.action == 'test':
            result = sku.test(args.work)
        else:
            result = globals()[args.action.replace('-', '_')](args.work)
        print(result)


if __name__ == '__main__':
    main()
