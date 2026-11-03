"""Explicit SKU draft migration, API and drained native release; preserve Skill and settings."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('sku_runtime', Path(__file__).with_name('sku-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def state(work,tested=False):
    data = json.loads((work/'prepared.json').read_text())
    source = Path(data['source'])
    r.require(r.digest(source/'release.json') == data['manifest'],'Manifest drift')
    manifest = r.verify_package(source)
    r.require(data['native'] == manifest['native'] and data['patch'] == manifest['api']['files'],
              'Prepared source baseline drift')
    r.require(all(r.digest(p)==h for p,h in data['compose']['files'].items()),'Compose drift')
    r.require(r.hashes(data['image']) == {n:v['sha256'] for n,v in data['patch'].items()},'Image drift')
    r.require(r.digest(work/'api-overlay.json') == data['overlayHash'],'Overlay drift')
    # The API is deliberately stopped during gate/backup. Compare only protected resources here.
    protected = data['protected']
    r.helper('sku-native').guard(work, data)
    r.require(r.b.tree(Path('/var/lib/hengxin-overseas/local-skills')) == protected['skills'],'Skill bytes drift')
    for name,saved in protected['containers'].items():
        if name == r.API:
            continue
        live = json.loads(r.run('docker','inspect',name))[0]
        r.require(dict(id=live['Id'],image=live['Image'],running=live['State']['Running']) == saved,'Unrelated container drift')
    if tested:
        r.require(json.loads((work/'INSTALL_TESTS_PASSED').read_text()) ==
                  {'manifest':data['manifest'],'image':data['image']},'Installed tests missing')
    return data,source


def prepare(work,source,secret_file):
    r.require(not (work/'prepared.json').exists(),'Inspect existing preparation')
    manifest,live = r.verify_package(source),r.inspect()
    environment = r.helper('sku-environment')
    secret = environment.credential(secret_file)
    r.require(live['State']['Running'] and live['Image'] == manifest['api']['image'],'API baseline drift')
    r.require(r.hashes(live['Image']) == {n:v['baseline'] for n,v in manifest['api']['files'].items()},'Live source drift')
    protected = r.b.snapshot()
    r.require(protected['frontendVersion'] == '0.2.59','Frontend baseline drift')
    r.require(r.sql(r.DB,'SELECT version_num FROM overseas_alembic_version') == 'overseas_0025','Schema drift')
    data = dict(source=str(source),manifest=r.digest(source/'release.json'),oldId=live['Id'],oldImage=live['Image'],
                compose=r.a.compose_info(live),patch=manifest['api']['files'],native=manifest['native'],protected=protected,
                environment={'api':r.environment_hash(environment.expected_environment(live['Config']['Env'], secret)),
                             'native':{unit:r.native_environment(unit) for unit in r.UNITS}})
    r.helper('sku-native').preflight(data)
    before = json.loads(r.a.compose(data['compose'],'config','--format','json'))
    r.a.check_live_config(live,before)
    context = work/'api-build'
    context.mkdir(mode=0o755)
    for name in r.FILES:
        target = context/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/'api'/name,target)
    for path in context.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    tag = 'hengxin-smart-image-backend:'+manifest['release']
    r.require(not r.run('docker','images','-q',tag),'Release tag exists')
    r.run('docker','tag',live['Image'],tag+'-base')
    (context/'Dockerfile').write_text('FROM '+tag+'-base\n'+''.join('COPY '+n+' /app/'+n+'\n' for n in sorted(r.FILES)))
    r.run('docker','build','--network=none','--pull=false','-t',tag,str(context),timeout=180)
    data['image'] = r.run('docker','image','inspect','--format','{{.Id}}',tag)
    overlay = work/'api-overlay.json'
    r.private(overlay,environment.overlay(data['image'], secret))
    after = json.loads(r.a.compose(data['compose'],'config','--format','json',overlay=overlay))
    before['services']['api']['image'] = data['image']
    before['services']['api'].setdefault('environment', {})[environment.KEY] = secret
    r.require(after == before, 'API overlay changes unrelated settings')
    r.require(r.run('docker','run','--rm','--network','none','--read-only','--entrypoint','python',
        data['image'],'-B','-c',"import httpx; assert httpx.__version__ == '0.28.1'; print('HTTPX_READY')") == 'HTTPX_READY',
        'Pinned runtime HTTPX unavailable')
    data['overlayHash'] = r.digest(overlay)
    r.unchanged(protected)
    r.private(work/'prepared.json',data)
    r.private(work/'RECOVERY.txt','Before MIGRATION_STARTED/API_SWITCH_STARTED: recover-before-switch restores old services. '
        'After migration starts: keep API stopped and repair forward; never restore/downgrade the live database. '
        'Native partial replacement: saved native-backup.json proves original bytes; finish only pinned patch files while '
        'both units are stopped. Do not overwrite backup. Graceful stop timeout: retain runtime stop protection; '
        'never SIGKILL or remove protection while a stop is pending.\n')
    state(work)
    return 'PREPARED_NO_LIVE_SERVICE_CHANGED'


def installed_pytest(command,work):
    def decoded(value):
        return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else value or ''
    try:
        result = subprocess.run(command,capture_output=True,text=True,timeout=600)
    except subprocess.TimeoutExpired as error:
        r.private(work/'installed-tests.txt',decoded(error.stdout)+'\n--- STDERR ---\n'+decoded(error.stderr)+
                  '\nINSTALL_TEST_TIMEOUT: 600 seconds\n')
        raise
    output = result.stdout+'\n--- STDERR ---\n'+result.stderr
    r.private(work/'installed-tests.txt',output)
    r.require(result.returncode == 0 and 'passed' in result.stdout and
              'failed' not in result.stdout and 'skipped' not in result.stdout,
              'Installed tests incomplete; inspect private installed-tests.txt')
    return output


def test(work):
    data,source = state(work)
    (work/'INSTALL_TESTS_PASSED').unlink(missing_ok=True)
    name = 'hx-sku-tests-'+data['manifest'][:12]
    created = False
    try:
        pgimage = json.loads(r.run('docker','inspect',r.PG))[0]['Image']
        r.run('docker','run','--rm','-d','--network','none','--name',name,
              '--mount','type=volume,dst=/var/lib/postgresql/data','-e','POSTGRES_HOST_AUTH_METHOD=trust',pgimage)
        created = True
        deadline = time.monotonic()+45
        while True:
            try:
                r.run('docker','exec',name,'pg_isready','-h','127.0.0.1','-U','postgres',timeout=4)
                break
            except RuntimeError:
                r.require(time.monotonic()<deadline,'Test database readiness timeout')
                time.sleep(0.5)
        r.run('docker','exec',name,'createdb','-h','127.0.0.1','-U','postgres','sku_test')
        url = 'postgresql+psycopg://postgres@127.0.0.1/sku_test'
        command = ['docker','run','--rm','--network','container:'+name,'--read-only','--tmpfs','/tmp:rw,nosuid',
            '--mount','type=bind,src='+str(source/'tests')+',dst=/app/tests,readonly',
            '-e','PYTHONPATH=/app','-e','TEST_OVERSEAS_DATABASE_URL='+url,'-e','TEST_OVERSEAS_MEMBERS_DATABASE_URL='+url,
            '--entrypoint','python',data['image'],'-B','-m','pytest','-q','-p','no:cacheprovider',
            *['/app/tests/'+name for name in r.TESTS]]
        output = installed_pytest(command,work)
        r.private(work/'INSTALL_TESTS_PASSED',{'manifest':data['manifest'],'image':data['image']})
        return output
    finally:
        if created:
            r.run('docker','rm','-f','-v',name)


def gate(work):
    data,_ = state(work,tested=True)
    r.require(not (work/'gate.json').exists() and not (work/'GATE_STARTED').exists(),'Inspect previous gate attempt')
    r.require(r.inspect()['Id'] == data['oldId'],'API baseline changed')
    node = r.worker('idle')['node']
    r.private(work/'GATE_STARTED',{'node':node,'oldId':data['oldId']})
    # Docker's -1 daemon timeout never escalates to SIGKILL; the caller is bounded.
    # A manual stop also suppresses restart-policy races while the write gate is closed.
    r.run('docker','stop','--time','-1',r.API,timeout=60)
    r.require(not r.inspect()['State']['Running'],'API stop unconfirmed')
    r.worker('idle')  # If a submit raced with stop, leave consumer running; operator can recover/retry.
    paused = r.worker('pause')
    r.require(paused['node'] == node,'Worker identity changed')
    r.private(work/'gate.json',{'node':node,'manifest':data['manifest'],'phase':'api-stopped-consumer-paused'})
    r.helper('sku-native').stop(work, data)
    return 'API_STOPPED_IDLE_CONSUMER_PAUSED_NATIVE_GRACEFULLY_STOPPED'


def recover_before_switch(work):
    data,_ = state(work,tested=True)
    r.require(not (work/'API_SWITCH_STARTED').exists() and not (work/'MIGRATION_STARTED').exists(),
              'Migration/API switch begun: inspect forward recovery')
    r.require(r.sql(r.DB,'SELECT version_num FROM overseas_alembic_version') == 'overseas_0025','Schema changed')
    node = json.loads((work/'GATE_STARTED').read_text())['node']
    r.require(r.inspect()['Id'] == data['oldId'],'Old API identity changed')
    if (work/'NATIVE_STOP_STARTED').exists():
        r.helper('sku-native').start(work, data, recovery=True)
    else:
        r.worker('resume',node)
    r.run('docker','start',r.API)
    r.helper('image-cache-runtime').readiness('http://127.0.0.1:18018/api/overseas/v1/health/ready')
    r.private(work/'RECOVERED_BEFORE_SWITCH',{'node':node,'oldId':data['oldId']})
    return 'OLD_API_AND_CONSUMER_RECOVERED_INSPECT_BEFORE_NEW_ATTEMPT'


def native(work):
    data,source = state(work,tested=True)
    return r.helper('sku-native').install(work,data,source)


def migrate(work):
    data,_ = state(work,tested=True)
    return r.helper('sku-database').migrate(work,data)


def api(work):
    data,_ = state(work,tested=True)
    r.require((work/'MIGRATION_VERIFIED').exists() and (work/'NATIVE_VERIFIED').exists(),
              'Verified migration and native restart required')
    r.require(json.loads((work/'MIGRATION_VERIFIED').read_text()) ==
              {'manifest':data['manifest'],'revision':r.REVISION}, 'Migration proof drift')
    r.helper('sku-native').verified(work,data)
    r.require(r.inspect()['Id'] == data['oldId'],'API baseline changed')
    r.require(r.sql(r.DB,'SELECT version_num FROM overseas_alembic_version') == r.REVISION,'Schema drift')
    r.worker_probe('overseas','verify',work)
    r.private(work/'API_SWITCH_STARTED',{'image':data['image']})
    r.a.compose(data['compose'],'up','-d','--no-deps','--no-build','api',overlay=work/'api-overlay.json')
    return verify(work)


def verify(work):
    data,_ = state(work,tested=True)
    r.helper('sku-native').verified(work,data)
    live = r.inspect()
    r.require(live['Image']==data['image'] and live['State']['Running'],'New API not running')
    r.require(r.sql(r.DB,'SELECT version_num FROM overseas_alembic_version') == r.REVISION,'Schema drift')
    r.a.check_live_config(live,json.loads(r.a.compose(data['compose'],'config','--format','json',overlay=work/'api-overlay.json')))
    r.require(r.environment_hash(live['Config']['Env']) == data['environment']['api'], 'API environment changed')
    r.helper('image-cache-runtime').readiness('http://127.0.0.1:18018/api/overseas/v1/health/ready')
    r.private(work/'API_VERIFIED',{'manifest':data['manifest'],'image':data['image'],'id':live['Id']})
    return 'API_0.2.60_AND_NATIVE_VERIFIED_SKILLS_UNCHANGED'


def resume(work):
    data,_ = state(work,tested=True)
    verify(work)
    node = json.loads((work/'gate.json').read_text())['node']
    r.worker_probe('overseas','verify',work)
    r.private(work/'RESUMED',{'manifest':data['manifest'],'node':node})
    return 'RELEASE_VERIFIED_NEW_NATIVE_CONSUMER_ACTIVE'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','test','gate','backup','migrate','native','api','verify','resume','recover-before-switch'))
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--secret-file',type=Path)
    args = parser.parse_args()
    r.require(os.geteuid() == 0,'Root required')
    os.umask(0o077)
    args.work.mkdir(parents=True,exist_ok=True)
    import fcntl
    with (args.work/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action == 'prepare':
            r.require(args.secret_file is not None, 'prepare requires --secret-file')
            result = prepare(args.work,args.source.resolve(),args.secret_file)
        elif args.action == 'backup':
            data,_ = state(args.work,tested=True)
            result = r.helper('sku-database').backup(args.work,data)
        else:
            result = globals()[args.action.replace('-','_')](args.work)
        print(result)


if __name__ == '__main__':
    main()
