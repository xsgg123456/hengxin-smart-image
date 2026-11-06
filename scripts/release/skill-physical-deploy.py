"""Explicit physical-Skill cutover. No migration, GC, model calls or database rewind."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import time

spec = importlib.util.spec_from_file_location('physical', Path(__file__).with_name('skill-physical-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.r


def inspect(name):
    return json.loads(r.run('docker', 'inspect', name))[0]


def check_service(live, config, name):
    adapted = copy.deepcopy(config)
    adapted['services']['api'] = config['services'][name]
    r.a.check_live_config(live, adapted)


def state(work, tested=False, release=False, accepting_maintenance=False):
    data = json.loads((work/'prepared.json').read_text())
    source = Path(data['source'])
    r.require(r.digest(source/'release.json') == data['manifest'], 'Manifest drift')
    manifest = r.verify_package(source)
    r.require(not release or manifest['mode'] == 'release', 'Candidate cannot change production')
    r.require(data['patch'] == manifest['api']['files'] and data['native'] == manifest['native'], 'Prepared scope drift')
    for chain in ('compose', 'publisherCompose'):
        r.require(all(r.digest(path) == value for path, value in data[chain]['files'].items()), 'Compose drift')
    r.require(r.digest(work/'api-overlay.json') == data['overlayHash'], 'Overlay drift')
    for role, image in data['images'].items():
        r.require(r.hashes(image) == {n: v['sha256'] for n, v in manifest[role]['files'].items()}, 'Image bytes drift')
    r.require(r.sql(r.DB, 'SELECT version_num FROM overseas_alembic_version') == r.REVISION, 'Schema drift')
    p.reuse.guard(work, data)
    r.helper('skill-reuse-gate').guard(work, data)
    if accepting_maintenance:
        r.require((work/'MAINTENANCE_STARTED').exists() and not (work/'RESUMED').exists(),
                  'No closed-window maintenance to accept')
    else:
        r.require(r.b.tree(Path(p.SKILL_ROOT)) == r.helper('skill-physical-maintenance').expected_skills(work, data),
                  'Skill tree differs from pinned baseline/accepted maintenance receipt')
    for name, saved in data['protected']['containers'].items():
        if name in (r.API, p.PUBLISHER):
            continue
        live = inspect(name)
        r.require(dict(id=live['Id'], image=live['Image'], running=live['State']['Running']) == saved,
                  'Unrelated container changed: '+name)
    if not (work/'FRONTEND_STARTED').exists():
        r.require(all(r.digest(r.a.APP/name) == value for name, value in data['protected']['frontend'].items()),
                  'Frontend baseline drift')
    if tested:
        proof = json.loads((work/'INSTALL_TESTS_PASSED').read_text())
        r.require(proof['manifest'] == data['manifest'] and proof['images'] == data['images'] and
                  r.b.tree(Path(proof['root'])/'app') == proof['source'], 'Installed tests missing/drifted')
    return data, source


def build(work, source, manifest, role):
    context = work/(role+'-build')
    context.mkdir(mode=0o755)
    context.chmod(0o755)
    for name in sorted(r.FILES):
        target = context/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source/'api'/name, target)
    for path in context.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    tag = 'hengxin-smart-image-backend:'+manifest['release']+'-'+role
    r.require(not r.run('docker', 'images', '-q', tag), 'Release image tag already exists')
    r.run('docker', 'tag', manifest[role]['image'], tag+'-base')
    (context/'Dockerfile').write_text('FROM '+tag+'-base\n'+''.join('COPY '+n+' /app/'+n+'\n' for n in sorted(r.FILES)))
    r.run('docker', 'build', '--network=none', '--pull=false', '-t', tag, str(context), timeout=180)
    return r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', tag)


def prepare(work, source):
    r.require(not (work/'prepared.json').exists(), 'Existing preparation must not be overwritten')
    manifest = r.verify_package(source)
    api, publisher = r.inspect(), inspect(p.PUBLISHER)
    for role, live in (('api', api), ('publisher', publisher)):
        r.require(live['State']['Running'] and live['Image'] == manifest[role]['image'], role+' baseline drift')
        r.require(r.hashes(live['Image']) == {n: v['baseline'] for n, v in manifest[role]['files'].items()},
                  role+' baseline source drift')
    protected = r.b.snapshot()
    r.require(protected['frontendVersion'] == r.BASE_VERSION, 'Frontend baseline drift')
    execution = r.helper('skill-reuse-preserve').execution_root()
    r.require(execution == p.EXECUTION_ROOT, 'Actual native history root differs')
    for value, mode, gid in ((p.SKILL_ROOT, 0o755, 0), (p.TRANSFER_ROOT, 0o700, 0), (p.SOCKET_ROOT, 0o750, 10001)):
        info = r.helper('sku-native').safe(Path(value)).stat()
        r.require(info.st_uid == 0 and info.st_gid == gid and stat.S_IMODE(info.st_mode) == mode,
                  'Existing publisher directory owner/mode differs')
    mounts = {m['Destination']: m for m in api['Mounts']}
    r.require(mounts[p.SKILL_ROOT]['Source'] == p.SKILL_ROOT and not mounts[p.SKILL_ROOT]['RW'],
              'API skill library must remain read-only')
    data = dict(source=str(source), manifest=r.digest(source/'release.json'), oldId=api['Id'], oldImage=api['Image'],
        oldPublisher=dict(id=publisher['Id'], image=publisher['Image']), compose=r.a.compose_info(api),
        publisherCompose=r.a.compose_info(publisher), patch=manifest['api']['files'], native=manifest['native'],
        protected=protected, executionRoot=execution,
        currentRelease=json.loads((Path(p.SKILL_ROOT)/'current.json').read_text())['release'], environment={
            'api': r.environment_hash(api['Config']['Env']),
            'native': {u: r.native_environment(u) for u in r.UNITS}})
    r.helper('sku-native').preflight(data)
    before = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json'))
    check_service(api, before, 'api')
    check_service(publisher, before, 'skill-publisher')
    data['images'] = {role: build(work, source, manifest, role) for role in ('api', 'publisher')}
    data['image'] = data['images']['api']
    r.private(work/'api-overlay.json', p.overlay(before, data['images']))
    after = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json', overlay=work/'api-overlay.json'))
    p.check_overlay(before, after, data['images'])
    data['overlayHash'] = r.digest(work/'api-overlay.json')
    data['proxies'] = r.helper('skill-reuse-gate').save(work)
    r.private(work/'prepared.json', data)
    state(work)
    return 'PREPARED_IMAGES_BUILT_NO_PRODUCTION_SWITCH'


def test(work):
    data, source = state(work)
    r.helper('skill-physical-test').candidate(work, data, source)
    state(work, tested=True)
    return 'API_PUBLISHER_NATIVE_ISOLATED_TESTS_PASSED'


def idle(timeout=30):
    helper = r.helper('skill-reuse-deploy')
    helper.r = r
    return helper.idle(timeout)


def stop_container(name):
    # Never escalate to SIGKILL if a request or publisher transaction is still finishing.
    r.run('docker', 'stop', '--time', '-1', name, timeout=60)
    r.require(not inspect(name)['State']['Running'], 'Container graceful stop unconfirmed: '+name)


def gate(work):
    data, _ = state(work, tested=True, release=True)
    r.require(not (work/'GATE_STARTED').exists(), 'Interrupted gate: recover first')
    r.require(r.inspect()['Id'] == data['oldId'] and inspect(p.PUBLISHER)['Id'] == data['oldPublisher']['id'],
              'Service baseline identity changed')
    node = idle()
    r.private(work/'GATE_STARTED', dict(node=node, manifest=data['manifest']))
    r.helper('skill-reuse-gate').set_gate(work, data, True)
    deadline = time.monotonic()+180
    stable = 0
    while stable < 2:
        budget = deadline-time.monotonic()
        r.require(budget > 0, 'Drain timed out; keep gate and running native')
        try:
            r.require(idle(min(20, budget)) == node, 'Worker identity drift')
            stable += 1
        except RuntimeError:
            stable = 0
        if stable < 2:
            time.sleep(min(2, max(0, deadline-time.monotonic())))
    stop_container(r.API)
    stop_container(p.PUBLISHER)
    r.require(idle() == node, 'Work appeared after admission stopped')
    r.require(r.worker('pause')['node'] == node, 'Worker changed')
    r.private(work/'gate.json', dict(node=node, manifest=data['manifest'], phase='api-stopped-consumer-paused'))
    r.helper('sku-native').stop(work, data)
    r.helper('skill-reuse-preserve').capture(work, data)
    return 'DUAL_GATE_CLOSED_DRAINED_ALL_OVERSEAS_WRITERS_STOPPED'


def backup(work):
    data, _ = state(work, tested=True, release=True)
    r.helper('skill-reuse-gate').require_closed(work, data)
    r.require(not inspect(p.PUBLISHER)['State']['Running'], 'Publisher must remain stopped')
    result = r.helper('polling-database').backup(work, data)
    r.helper('skill-reuse-native').backup(work, data)
    r.helper('skill-reuse-native').records(work, data)
    return result


def native(work):
    data, source = state(work, tested=True, release=True)
    return r.helper('skill-physical-native').install(work, data, source)


def publisher_ready(data):
    live = inspect(p.PUBLISHER)
    r.require(live['Image'] == data['images']['publisher'] and live['State']['Running'] and
              live['Config']['User'] == '0:0' and not live['HostConfig'].get('PortBindings'), 'Publisher identity/ports drift')
    expected = {path: (path, True) for path in (p.SKILL_ROOT, p.TRANSFER_ROOT, p.SOCKET_ROOT, p.EXECUTION_ROOT)}
    r.require({m['Destination']: (m['Source'], m['RW']) for m in live['Mounts']} == expected,
              'Publisher must bind the actual native history root explicitly')
    env = dict(item.split('=', 1) for item in live['Config']['Env'])
    r.require(env.get('OVERSEAS_CODEX_EXECUTION_ROOT') == p.EXECUTION_ROOT, 'Publisher history setting drift')
    socket = Path(p.SOCKET_ROOT)/'publisher.sock'
    info = socket.stat()
    r.require(stat.S_ISSOCK(info.st_mode) and info.st_uid == 0 and info.st_gid == 10001 and
              stat.S_IMODE(info.st_mode) == 0o660, 'Publisher socket permission drift')
    code = ('import httpx,os; assert os.geteuid()==10001; '
        'c=httpx.Client(transport=httpx.HTTPTransport(uds='+repr(str(socket))+'),base_url="http://publisher",timeout=2); '
        's=c.get("/health"); assert s.status_code==200 and s.json()=={"status":"ok"}; print("OK")')
    r.require(r.run('docker', 'exec', '--user', '10001:10001', p.PUBLISHER, 'python', '-B', '-c', code, timeout=5) == 'OK',
              'Publisher UDS inaccessible as API uid')


def switch(work):
    data, source = state(work, tested=True, release=True)
    r.helper('skill-reuse-gate').require_closed(work, data)
    r.helper('sku-native').stopped()
    r.helper('polling-database').backup_verified(work, data)
    r.require(json.loads((work/'INSTALLED_PATH_TESTS_PASSED').read_text()) == {'manifest': data['manifest']},
              'Final native tests missing')
    r.private(work/'API_SWITCH_STARTED', {'manifest': data['manifest']})
    r.a.compose(data['compose'], 'up', '-d', '--no-deps', '--no-build', 'skill-publisher', 'api',
                overlay=work/'api-overlay.json')
    deadline = time.monotonic()+45
    while True:
        try:
            publisher_ready(data)
            break
        except (RuntimeError, OSError):
            r.require(time.monotonic() < deadline, 'Publisher startup deadline; retain gate')
            time.sleep(.5)
    # Reload nginx DNS/upstream while both admission gates stay closed.
    saved = data['proxies']['web']
    r.run('docker', 'exec', saved['id'], 'nginx', '-t')
    r.run('docker', 'exec', saved['id'], 'nginx', '-s', 'reload')
    r.helper('skill-reuse-gate').require_closed(work, data)
    r.private(work/'FRONTEND_STARTED', {'manifest': data['manifest']})
    r.helper('sku-frontend').deploy(source, r.a.APP, work/'frontend-backup')
    r.helper('skill-reuse-preserve').verify(work, data)
    r.helper('sku-native').start(work, data)
    return verify(work)


def verify(work):
    return r.helper('skill-physical-recovery').verify(__import__('types').SimpleNamespace(**globals()), work)


def maintenance(work):
    verify(work)
    data, _ = state(work, tested=True, release=True)
    return r.helper('skill-physical-maintenance').begin(work, data)


def accept_maintenance(work, receipt):
    data, _ = state(work, tested=True, release=True, accepting_maintenance=True)
    result = r.helper('skill-physical-maintenance').accept(work, data, receipt)
    verify(work)
    return result


def resume(work):
    return r.helper('skill-physical-recovery').resume(__import__('types').SimpleNamespace(**globals()), work)


def recover(work):
    return r.helper('skill-physical-recovery').recover(__import__('types').SimpleNamespace(**globals()), work)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'test', 'gate', 'backup', 'native', 'switch', 'verify',
        'maintenance', 'accept-maintenance', 'resume', 'recover'))
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    r.require(os.geteuid() == 0 and not __import__('sys').flags.optimize, 'Root/non-optimized Python required')
    os.umask(0o077)
    args.work = args.work.resolve()
    args.work.mkdir(parents=True, exist_ok=True)
    r.helper('sku-native').safe(args.work)
    store = r.helper('release-retention-state').Store()
    with store.locked():
        claim = store.root/'native-release-owner.json'
        owner = {'work': str(args.work)}
        if claim.exists():
            r.require(json.loads(claim.read_text()) == owner, 'Another release owns admission')
        if args.action == 'gate' and not claim.exists():
            state(args.work, tested=True, release=True)
            r.private(claim, owner)
        if args.action == 'prepare':
            r.require(args.source is not None, 'prepare requires --source')
            result = prepare(args.work, args.source.resolve())
        elif args.action == 'accept-maintenance':
            r.require(args.receipt is not None, 'accept-maintenance requires --receipt')
            result = accept_maintenance(args.work, args.receipt.resolve())
        else:
            result = globals()[args.action](args.work)
        if args.action in ('resume', 'recover') and claim.exists():
            claim.unlink()
        print(result)


if __name__ == '__main__':
    main()
