"""Bounded prepare/test/gate/backup/native/publisher/API/static/verify and recovery."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import time
import hashlib
import urllib.request

spec = importlib.util.spec_from_file_location('folders_runtime',Path(__file__).with_name('skill-folders-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.r
sku = r.helper('sku-deploy')
recovery = r.helper('skill-folders-recovery')

def state(work,tested=False,release=False):
    data,source = sku.state(work,tested)
    if release:
        r.require(r.verify_package(source)['mode'] == 'release','Candidate cannot change production')
    r.require(r.sql(r.DB,'SELECT version_num FROM overseas_alembic_version') == r.REVISION,'Schema drift')
    return data,source

def mount(source,target,readonly=False):
    return {'type':'bind','source':source,'target':target,'read_only':readonly}

def overlay(before,image):
    api = before['services']['api']
    existing = api.get('environment',{})
    keep = ('OVERSEAS_DATABASE_URL','OVERSEAS_APP_ENV','OVERSEAS_LOCAL_SKILL_ROOT',
        'OVERSEAS_SKILL_TOGGLE_OWNER_ID','OVERSEAS_FULL_ACCESS_MEMBER_IDS','OVERSEAS_WORKFLOW_COLLABORATOR_MEMBER_IDS',
        'OVERSEAS_DB_POOL_SIZE','OVERSEAS_DB_MAX_OVERFLOW')
    env = {k:existing[k] for k in keep if k in existing}
    r.require(all(env.get(k) for k in ('OVERSEAS_DATABASE_URL','OVERSEAS_APP_ENV','OVERSEAS_LOCAL_SKILL_ROOT')),
              'Required publisher environment missing')
    # Shared Settings requires these unrelated fields; never give the root publisher their production credentials.
    env.update(HX_BUSINESS_CONTEXT='overseas',OVERSEAS_REDIS_URL='redis://127.0.0.1:1/0',
        OVERSEAS_MINIO_ENDPOINT='127.0.0.1:1',OVERSEAS_MINIO_ACCESS_KEY='publisher-unused',
        OVERSEAS_MINIO_SECRET_KEY='publisher-unused',OVERSEAS_MINIO_BUCKET='publisher-unused',
        OVERSEAS_CODEX_EXECUTION_ROOT='/tmp/publisher-unused-execution',OVERSEAS_SKILL_INSTALL_ROOT='/tmp/publisher-unused-skills',
        OVERSEAS_DB_APPLICATION_NAME='hx-skill-publisher')
    env.update(HX_SKILL_PUBLISH_SOCKET=p.SOCKET_ROOT+'/publisher.sock',HX_SKILL_TRANSFER_ROOT=p.TRANSFER_ROOT)
    publisher = dict(image=image,container_name=p.PUBLISHER,user='0:0',restart='unless-stopped',
        command=['python','-B','-m','app.overseas.management.skill_publisher'],environment=env,
        volumes=[mount(p.SKILL_ROOT,p.SKILL_ROOT),mount(p.TRANSFER_ROOT,p.TRANSFER_ROOT),
                 mount(p.SOCKET_ROOT,p.SOCKET_ROOT)],read_only=True,tmpfs=['/tmp:rw,nosuid,noexec,size=64m'],
        security_opt=['no-new-privileges:true'],stop_grace_period='2m')
    if api.get('networks'):
        publisher['networks'] = copy.deepcopy(api['networks'])
    return {'services':{'api':{'image':image,'environment':{'HX_SKILL_PUBLISH_SOCKET':p.SOCKET_ROOT+'/publisher.sock'},
        'volumes':[mount(p.SOCKET_ROOT,p.SOCKET_ROOT,True)]},'skill-publisher':publisher}}

def prepare(work,source):
    r.require(not (work/'prepared.json').exists(),'Inspect previous preparation')
    manifest,live = r.verify_package(source),r.inspect()
    r.require(live['State']['Running'] and live['Image'] == r.BASE_IMAGE,'API baseline drift')
    r.require(r.hashes(live['Image']) == {n:v['baseline'] for n,v in manifest['api']['files'].items()},'Source drift')
    r.require(not r.run('docker','ps','-aq','--filter','name=^/'+p.PUBLISHER+'$'),'Publisher already exists')
    protected = r.b.snapshot()
    r.require(protected['frontendVersion'] == r.BASE_VERSION,'Frontend baseline drift')
    r.require(r.sql(r.DB,'SELECT version_num FROM overseas_alembic_version') == r.REVISION,'Schema drift')
    data = dict(source=str(source),manifest=r.digest(source/'release.json'),oldId=live['Id'],oldImage=live['Image'],
        compose=r.a.compose_info(live),patch=manifest['api']['files'],native=manifest['native'],protected=protected,
        environment={'api':r.environment_hash(live['Config']['Env']),
                     'native':{u:r.native_environment(u) for u in r.UNITS}})
    r.helper('sku-native').preflight(data)
    before = json.loads(r.a.compose(data['compose'],'config','--format','json'))
    r.a.check_live_config(live,before)
    context = work/'api-build'
    context.mkdir(mode=0o755)
    for name in sorted(r.FILES):
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
    config = overlay(before,data['image'])
    r.private(work/'api-overlay.json',config)
    after = json.loads(r.a.compose(data['compose'],'config','--format','json',overlay=work/'api-overlay.json'))
    expected = copy.deepcopy(before)
    expected['services']['api']['image'] = data['image']
    expected['services']['api'].setdefault('environment',{})['HX_SKILL_PUBLISH_SOCKET'] = p.SOCKET_ROOT+'/publisher.sock'
    api_after = copy.deepcopy(after['services']['api'])
    added = [v for v in api_after['volumes'] if v['target'] == p.SOCKET_ROOT]
    r.require(len(added)==1 and added[0]['source']==p.SOCKET_ROOT and added[0]['read_only'], 'Socket mount mismatch')
    api_after['volumes'] = [v for v in api_after['volumes'] if v['target'] != p.SOCKET_ROOT]
    r.require(api_after == expected['services']['api'],'API configuration changes beyond socket/image')
    after_without = copy.deepcopy(after)
    after_without['services']['api'] = before['services']['api']
    del after_without['services']['skill-publisher']
    r.require(after_without == before,'Unrelated Compose configuration changed')
    data['overlayHash'] = r.digest(work/'api-overlay.json')
    r.unchanged(protected)
    r.private(work/'prepared.json',data)
    r.private(work/'RECOVERY.txt','No migration. Candidate cannot gate. Before API_SWITCH_STARTED use recover-before-switch. '
        'After switch use rollback. Never restore database dump over live data. Native partial patch: repair-native only '
        'while both units stopped. Graceful stop timeout: keep protection, never force-kill. Do not delete Skill releases '
        'or transfer state during rollback; freeze new catalog writes by stopping publisher.\n')
    state(work)
    return 'PREPARED_NO_PRODUCTION_SWITCH'

def test(work):
    return sku.test(work)

def imports_idle():
    r.require(r.sql(r.DB,"SELECT count(*) FROM overseas_draft_imports WHERE state IN ('queued','running')") == '0',
              'Draft imports active')

def gate(work):
    data,_ = state(work,tested=True,release=True)
    r.require(not (work/'GATE_STARTED').exists(),'Inspect previous gate')
    r.require(r.inspect()['Id'] == data['oldId'],'API identity changed')
    imports_idle()
    node = r.worker('idle')['node']
    r.private(work/'GATE_STARTED',{'node':node,'oldId':data['oldId']})
    r.run('docker','stop','--time','-1',r.API,timeout=60)
    r.require(not r.inspect()['State']['Running'],'API stop unconfirmed')
    imports_idle()
    r.worker('idle')
    r.require(r.worker('pause')['node'] == node,'Worker changed')
    r.private(work/'gate.json',{'node':node,'manifest':data['manifest'],'phase':'api-stopped-consumer-paused'})
    r.helper('sku-native').stop(work,data)
    return 'GATED_AND_DRAINED'

def backup(work):
    data,_ = state(work,tested=True,release=True)
    return r.helper('polling-database').backup(work,data)

def native(work):
    data,source = state(work,tested=True,release=True)
    return r.helper('skill-folders-native').install(work,data,source)

def publisher_ready(data,timeout=8):
    deadline = time.monotonic()+timeout
    live = json.loads(r.run('docker','inspect',p.PUBLISHER,timeout=timeout))[0]
    r.require(live['Image']==data['image'] and live['State']['Running'] and live['Config']['User']=='0:0',
              'Publisher identity mismatch')
    r.require(not live['HostConfig'].get('PortBindings'),'Publisher has public ports')
    expected = {s:(s,True) for s in (p.SKILL_ROOT,p.TRANSFER_ROOT,p.SOCKET_ROOT)}
    r.require({m['Destination']:(m['Source'],m['RW']) for m in live['Mounts']} == expected,'Publisher mount drift')
    socket = Path(p.SOCKET_ROOT)/'publisher.sock'
    info = socket.stat()
    import stat
    r.require(stat.S_ISSOCK(info.st_mode) and info.st_uid==0 and info.st_gid==10001 and
              stat.S_IMODE(info.st_mode)==0o660,'Publisher socket permissions mismatch')
    code = ('import httpx,os; assert os.geteuid()==10001; '
        'c=httpx.Client(transport=httpx.HTTPTransport(uds='+repr(str(socket))+'),base_url="http://publisher",timeout=2); '
        's=c.get("/health"); assert s.status_code==200 and s.json()=={"status":"ok"}; print("UDS_HEALTH_OK")')
    remaining = deadline-time.monotonic()
    r.require(remaining>0,'Publisher probe deadline')
    r.require(r.run('docker','exec','--user','10001:10001',p.PUBLISHER,'python','-B','-c',code,
                    timeout=remaining)=='UDS_HEALTH_OK','Publisher UDS health failed as API uid')
    return live

def publisher(work):
    data,_ = state(work,tested=True,release=True)
    r.require((work/'backup/COMPLETE').exists() and (work/'NATIVE_VERIFIED').exists(),'Backup/native verification missing')
    r.require(not r.inspect()['State']['Running'],'API must stay stopped')
    started = work/'PUBLISHER_START_STARTED'
    if not started.exists():
        r.require(not Path(p.SOCKET_ROOT).exists() and not Path(p.TRANSFER_ROOT).exists(),
                  'Publisher directory exists before this release')
        r.private(started,{'manifest':data['manifest']})
    r.require(json.loads(started.read_text()) == {'manifest':data['manifest']},'Publisher ownership mismatch')
    for value,mode,gid in ((p.SOCKET_ROOT,0o750,10001),(p.TRANSFER_ROOT,0o700,0)):
        path = r.helper('sku-native').safe(Path(value))
        if not path.exists():
            path.mkdir(mode=mode)
            os.chown(path,0,gid)
            path.chmod(mode)
        info = path.stat()
        r.require(info.st_uid==0 and info.st_gid==gid and info.st_mode & 0o777 == mode,'Publisher directory permissions drift')
    r.a.compose(data['compose'],'up','-d','--no-deps','--no-build','skill-publisher',overlay=work/'api-overlay.json')
    deadline = time.monotonic()+40
    while True:
        try:
            remaining = deadline-time.monotonic()
            r.require(remaining>0,'Publisher readiness deadline')
            publisher_ready(data,timeout=min(5,remaining))
            r.require(time.monotonic()<=deadline,'Publisher readiness deadline')
            break
        except (RuntimeError,OSError):
            r.require(time.monotonic()<deadline,'Publisher readiness deadline')
            time.sleep(0.5)
    r.private(work/'PUBLISHER_VERIFIED',{'manifest':data['manifest'],'image':data['image']})
    return 'ROOT_PUBLISHER_READY_SOCKET_ONLY'

def api(work):
    data,_ = state(work,tested=True,release=True)
    r.require(not (work/'API_SWITCH_STARTED').exists(),'Inspect previous API switch')
    publisher_ready(data)
    r.helper('sku-native').verified(work,data)
    r.private(work/'API_SWITCH_STARTED',{'manifest':data['manifest'],'image':data['image']})
    r.a.compose(data['compose'],'up','-d','--no-deps','--no-build','api',overlay=work/'api-overlay.json')
    r.helper('skill-folders-gateway').refresh(r,data)
    return verify(work)

def verify(work):
    data,_ = state(work,tested=True,release=True)
    live = r.inspect()
    r.require(live['Image']==data['image'] and live['State']['Running'],'New API not running')
    r.a.check_live_config(live,json.loads(r.a.compose(data['compose'],'config','--format','json',overlay=work/'api-overlay.json')))
    r.require(r.environment_hash(live['Config']['Env']) == data['environment']['api'],'Business environment drift')
    r.helper('sku-native').verified(work,data)
    publisher_ready(data)
    for port,path in ((18018,'/api/overseas/v1/health/ready'),(18080,'/api/v1/health/ready')):
        r.helper('image-cache-runtime').readiness('http://127.0.0.1:'+str(port)+path)
    check = ('import os,pathlib; p=pathlib.Path("'+p.SKILL_ROOT+'"); '
             'assert not os.access(p,os.W_OK); assert os.geteuid()==10001; '
             'from app.overseas.management.installed_catalog import catalog; catalog(); print("READ_ONLY_CATALOG_OK")')
    r.require(r.run('docker','exec',r.API,'python','-B','-c',check)=='READ_ONLY_CATALOG_OK','API runtime permission probe failed')
    r.helper('skill-folders-gateway').readiness(r)
    r.private(work/'API_VERIFIED',{'manifest':data['manifest'],'image':data['image'],'id':live['Id']})
    return 'API_NATIVE_PUBLISHER_VERIFIED'

def frontend(work):
    data,source = state(work,tested=True,release=True)
    verify(work)
    return r.helper('sku-frontend').deploy(source,r.a.APP,work/'frontend-backup')

def resume(work):
    data,source = state(work,tested=True,release=True)
    verify(work)
    for name,digest in r.verify_package(source)['files'].items():
        if name.startswith('frontend/'):
            r.require(r.digest(r.a.APP/name)==digest,'Installed frontend drift')
    refs = ['index.html',*r.helper('archive-runtime').entry_refs((source/'frontend/dist/index.html').read_text())]
    deadline = time.monotonic()+45
    for ref in refs:
        remaining = deadline-time.monotonic()
        r.require(remaining>0,'Static HTTP verification deadline')
        request = urllib.request.Request('https://zhitu.qhhengxin.top/'+ref,
            headers={'Accept-Encoding':'identity','Cache-Control':'no-cache'})
        with urllib.request.urlopen(request,timeout=min(10,remaining)) as response:
            r.require(response.status==200 and hashlib.sha256(response.read()).hexdigest()==
                r.digest(source/'frontend/dist'/ref),'Live static bytes mismatch')
    r.private(work/'RESUMED',{'manifest':data['manifest'],'image':data['image']})
    return 'RELEASE_VERIFIED_REQUIRES_BROWSER_VISUAL_ACCEPTANCE'

def stop_publisher(data):
    return recovery.stop_publisher(data,r,p)

def recover_before_switch(work):
    return recovery.recover_before_switch(work,r,p,state)

def rollback(work):
    return recovery.rollback(work,r,p,state,imports_idle)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','test','gate','backup','native','repair-native','publisher','api',
        'frontend','verify','resume','recover-before-switch','rollback'))
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--source',type=Path)
    args = parser.parse_args()
    r.require(os.geteuid()==0,'Root required')
    os.umask(0o077)
    args.work.mkdir(parents=True,exist_ok=True)
    import fcntl
    with (args.work/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='prepare':
            r.require(args.source is not None,'prepare requires source')
            result = prepare(args.work,args.source.resolve())
        else:
            result = globals()[args.action.replace('-','_') if args.action!='repair-native' else 'native'](args.work)
        print(result)

if __name__=='__main__':
    main()
