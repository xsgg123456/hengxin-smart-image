"""Native-only source cutover, protected by dual proxy admission and host-wide lock."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import time

spec = importlib.util.spec_from_file_location('reuse',Path(__file__).with_name('skill-reuse-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.r


def api_identity():
    live = r.inspect()
    r.require(live['State']['Running'], 'API must remain running')
    return dict(id=live['Id'],image=live['Image'],started=live['State']['StartedAt'])


def state(work,tested=False,release=False):
    data = json.loads((work/'prepared.json').read_text())
    source = Path(data['source'])
    r.require(r.digest(source/'release.json') == data['manifest'], 'Manifest drift')
    manifest = r.verify_package(source)
    r.require(data['native'] == manifest['native'] and data['patch'] == {
        n:{'sha256':manifest['files']['native/'+n]} for n in r.NATIVE_FILES}, 'Prepared scope drift')
    if release:
        r.require(manifest['mode'] == 'release', 'Candidate packages are test-only')
    r.require(api_identity() == data['api'], 'API restarted or changed')
    r.require(r.environment_hash(r.inspect()['Config']['Env']) == data['environment']['api'], 'API config drift')
    r.require(r.sql(r.DB,'SELECT version_num FROM overseas_alembic_version') == data['revision'], 'Schema drift')
    r.require(all(r.digest(path) == digest for path,digest in data['compose']['files'].items()), 'Compose drift')
    p.guard(work,data)
    r.helper('skill-reuse-gate').guard(work,data)
    r.require(r.b.tree(Path('/var/lib/hengxin-overseas/local-skills')) == data['protected']['skills'], 'Skill content drift')
    for name,saved in data['protected']['containers'].items():
        live = json.loads(r.run('docker','inspect',name))[0]
        r.require(dict(id=live['Id'],image=live['Image'],running=live['State']['Running']) == saved,
                  'Unrelated container drift')
    r.require(all(r.digest(r.a.APP/name) == digest for name,digest in data['protected']['frontend'].items()),
              'Frontend bytes drift')
    if tested:
        proof = json.loads((work/'INSTALL_TESTS_PASSED').read_text())
        r.require(proof['manifest'] == data['manifest'] and r.b.tree(Path(proof['root'])/'app') == proof['source'],
                  'Candidate installed tests missing/drifted')
    return data,source


def prepare(work,source):
    r.require(not (work/'prepared.json').exists(), 'Existing preparation must not be overwritten')
    manifest = r.verify_package(source)
    baseline = manifest['baseline']
    r.require(api_identity() == baseline['api'], 'API differs from measured baseline')
    protected = r.b.snapshot()
    r.require(r.sql(r.DB,'SELECT version_num FROM overseas_alembic_version') == baseline['revision'], 'Schema drift')
    for unit in r.UNITS:
        root = Path(protected['units'][unit]['cwd'])
        r.require(str(root) == baseline['roots'][unit] and
            r.digest(root/'app/overseas/studio/context_fs.py') == baseline['dependencies'][unit], 'Native dependency drift')
    data = dict(source=str(source),manifest=r.digest(source/'release.json'),api=baseline['api'],
        revision=baseline['revision'],compose=r.a.compose_info(r.inspect()),native=manifest['native'],
        patch={n:{'sha256':manifest['files']['native/'+n]} for n in r.NATIVE_FILES},protected=protected,
        environment={'api':r.environment_hash(r.inspect()['Config']['Env']),
                     'native':{u:r.native_environment(u) for u in r.UNITS}},
        executionRoot=r.helper('skill-reuse-preserve').execution_root())
    r.helper('sku-native').preflight(data)
    data['proxies'] = r.helper('skill-reuse-gate').save(work)
    r.private(work/'prepared.json',data)
    state(work)
    return 'PREPARED_NO_PRODUCTION_SERVICE_CHANGED'


def test(work):
    data,source = state(work)
    r.helper('skill-reuse-test').candidate(work,data,source)
    state(work,tested=True)
    return 'ISOLATED_NATIVE_INSTALL_TESTS_PASSED'


def idle(timeout=40):
    # Imports and deletion jobs must finish too; outbox may mutate persistent context.
    deadline = time.monotonic()+timeout
    for table,condition in (('overseas_draft_imports',"state IN ('queued','running')"),
                            ('overseas_task_deletions',"status='deleting'")):
        remaining = deadline-time.monotonic()
        r.require(remaining > 0, 'Drain observation deadline')
        count = r.run('docker','exec',r.DB[0],'psql','-v','ON_ERROR_STOP=1','-U',r.DB[1],'-d',r.DB[2],
            '-Atc','SELECT count(*) FROM '+table+' WHERE '+condition,timeout=remaining)
        r.require(count == '0', 'Background work remains')
    remaining = deadline-time.monotonic()
    r.require(remaining > 0, 'Drain observation deadline')
    return r.worker('idle',timeout=remaining)['node']


def gate(work):
    data,_ = state(work,tested=True,release=True)
    r.require(not (work/'GATE_STARTED').exists(), 'Interrupted gate: recover before new attempt')
    node = idle()
    r.private(work/'GATE_STARTED',dict(node=node,manifest=data['manifest']))
    r.helper('skill-reuse-gate').set_gate(work,data,True)
    # Proxy workers have finished old requests; poll bounded durable jobs without terminating them.
    deadline = time.monotonic()+180
    stable = 0
    while stable < 2:
        remaining = deadline-time.monotonic()
        r.require(remaining > 0, 'Tasks not drained; retain gate and running worker')
        try:
            r.require(idle(timeout=min(20,remaining)) == node, 'Worker node drift')
            stable += 1
        except RuntimeError:
            stable = 0
        if stable < 2:
            time.sleep(min(2,max(0,deadline-time.monotonic())))
    r.require(r.worker('pause')['node'] == node, 'Worker pause identity drift')
    r.private(work/'gate.json',dict(node=node,manifest=data['manifest']))
    r.helper('sku-native').stop(work,data)
    r.helper('skill-reuse-preserve').capture(work,data)
    return 'INTAKE_DRAINED_NATIVE_STOPPED_CONTEXT_FIXED'


def install(work):
    data,source = state(work,tested=True,release=True)
    r.helper('skill-reuse-native').install(work,data,source)
    return 'NATIVE_SOURCE_INSTALLED_AND_RESTARTED'


def verify(work):
    data,_ = state(work,tested=True,release=True)
    r.helper('sku-native').verified(work,data)
    r.require(json.loads((work/'INSTALLED_PATH_TESTS_PASSED').read_text()) == {'manifest':data['manifest']},
              'Actual installed-path regression missing')
    r.helper('skill-reuse-preserve').verify(work,data)
    for port,path in ((18018,'/api/overseas/v1/health/ready'),(18080,'/api/v1/health/ready')):
        r.helper('image-cache-runtime').readiness('http://127.0.0.1:'+str(port)+path)
    return 'NATIVE_HASHES_HEALTH_CONTEXT_ENVIRONMENT_VERIFIED'


def resume(work):
    verify(work)
    data,_ = state(work,tested=True,release=True)
    r.helper('skill-reuse-gate').set_gate(work,data,False)
    r.helper('skill-folders-gateway').readiness(r)
    r.private(work/'RESUMED',dict(manifest=data['manifest'],api=data['api']))
    return 'NATIVE_ONLY_RELEASE_COMPLETE_API_NEVER_RESTARTED'


def cancel_ungated(work,data):
    # Ownership is acquired before the first idle observation. A busy worker can
    # fail there without ever closing admission or changing a service.
    evidence = ('GATE_', 'PROXY_', 'INTAKE_', 'NATIVE_', 'native-backup',
                'gate.json', 'CONVERSATION_BASELINE', 'INSTALLED_PATH_TESTS_PASSED',
                'recovery-preserve', 'RESUMED', 'RECOVERED')
    r.require(not any(path.name.startswith(evidence) for path in work.iterdir()),
              'Missing gate start proof with cutover evidence; retain owner')
    native = r.helper('sku-native')
    native.preflight(data)
    r.helper('skill-reuse-native').verify_baseline(data)
    for unit in r.UNITS:
        r.require(native.pid(unit) == data['protected']['units'][unit]['pid'] and
                  r.run('systemctl','show',unit,'-p','ActiveState','--value') == 'active' and
                  r.run('systemctl','show',unit,'-p','Job','--value') in ('','0'),
                  'Original native service changed; retain owner')
    r.require(all(r.digest(saved['path']) == saved['sha256'] for saved in data['proxies'].values()),
              'Original proxy changed; retain owner')
    return 'UNGATED_RELEASE_CANCELLED_NO_SERVICE_CHANGED'


def recover(work):
    data,_ = state(work,tested=True,release=True)
    if not (work/'GATE_STARTED').exists():
        return cancel_ungated(work,data)
    node = json.loads((work/'GATE_STARTED').read_text())['node']
    r.helper('skill-reuse-gate').set_gate(work,data,True)
    if not (work/'gate.json').exists():
        r.private(work/'gate.json',dict(node=node,manifest=data['manifest']))
    native = r.helper('sku-native')
    for unit in r.UNITS:
        r.require(r.run('systemctl','show',unit,'-p','ActiveState','--value') in ('active','inactive') and
                  r.run('systemctl','show',unit,'-p','Job','--value') in ('','0'),
                  'Pending native stop: retain intake and no-SIGKILL protection')
    if (work/'NATIVE_PATCH_STARTED').exists() or (work/'NATIVE_RECOVERY.json').exists():
        for table,condition in (('overseas_draft_imports',"state IN ('queued','running')"),
                                ('overseas_task_deletions',"status='deleting'")):
            r.require(r.sql(r.DB,'SELECT count(*) FROM '+table+' WHERE '+condition) == '0',
                      'Recovery waits for background work; retain admission protection')
        r.helper('skill-reuse-native').restore(work,data)
    elif (work/'NATIVE_STOP_STARTED').exists():
        native.start(work,data,recovery=True)
    else:
        r.worker('resume',node)
    r.helper('skill-reuse-native').verify_baseline(data)
    preserve_work = work/'recovery-preserve' if (work/'recovery-preserve').exists() else work
    if (preserve_work/'CONVERSATION_BASELINE').exists():
        r.helper('skill-reuse-preserve').verify(preserve_work,data)
    r.helper('skill-reuse-gate').set_gate(work,data,False)
    state(work,tested=True,release=True)
    r.private(work/'RECOVERED',dict(manifest=data['manifest'],api=data['api']))
    return 'ORIGINAL_NATIVE_RESTORED_NO_DATABASE_OR_SESSION_REWIND'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','test','gate','install','verify','resume','recover'))
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--source',type=Path)
    args = parser.parse_args()
    r.require(os.geteuid() == 0 and not __import__('sys').flags.optimize, 'Root and non-optimized Python required')
    os.umask(0o077)
    args.work.mkdir(parents=True,exist_ok=True)
    r.helper('sku-native').safe(args.work)
    store = r.helper('release-retention-state').Store()
    with store.locked():
        claim = store.root/'native-release-owner.json'
        identity = {'work':str(args.work.resolve())}
        if claim.exists():
            r.require(json.loads(claim.read_text()) == identity, 'Another native release owns admission; recover it first')
        if args.action == 'gate' and not claim.exists():
            # Retain ownership across separate CLI phases and failures, not just during one flock.
            state(args.work,tested=True,release=True)
            r.private(claim,identity)
        if args.action == 'prepare':
            r.require(args.source is not None, 'prepare requires --source')
            result = prepare(args.work,args.source.resolve())
        else:
            result = globals()[args.action](args.work)
        if args.action in ('resume','recover') and claim.exists():
            claim.unlink()
        print(result)


if __name__ == '__main__':
    main()
