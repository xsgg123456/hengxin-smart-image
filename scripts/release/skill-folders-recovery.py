"""Recovery actions using the caller's pinned runtime and release guards."""
import json
from pathlib import Path

def stop_publisher(data,r,p):
    ids = r.run('docker','ps','-aq','--filter','name=^/'+p.PUBLISHER+'$')
    if ids:
        live = json.loads(r.run('docker','inspect',p.PUBLISHER))[0]
        r.require(live['Image']==data['image'] and live['Config']['User']=='0:0','Unexpected publisher identity')
        if live['State']['Running']:
            r.run('docker','stop','--time','-1',p.PUBLISHER,timeout=60)
        r.require(not json.loads(r.run('docker','inspect',p.PUBLISHER))[0]['State']['Running'],'Publisher stop unconfirmed')

def recover_before_switch(work,r,p,state):
    data,_ = state(work,tested=True,release=True)
    r.require(not (work/'API_SWITCH_STARTED').exists(),'Use rollback after switch')
    live = r.inspect()
    r.require(live['Id']==data['oldId'] and not live['State']['Running'],'Original API must be stopped')
    stop_publisher(data,r,p)
    if (work/'NATIVE_PATCH_STARTED').exists():
        r.require(r.b.tree(Path(p.SKILL_ROOT))==data['protected']['skills'],'Catalog changed; retain new reader and repair forward')
        # New reader can run safely without the publisher. Retain it during pre-switch recovery.
        r.helper('sku-native').start(work,data,recovery=True)
    elif (work/'NATIVE_STOP_STARTED').exists():
        r.helper('sku-native').start(work,data,recovery=True)
    else:
        r.worker('resume',json.loads((work/'GATE_STARTED').read_text())['node'])
    r.run('docker','start',r.API)
    r.helper('image-cache-runtime').readiness('http://127.0.0.1:18018/api/overseas/v1/health/ready')
    r.helper('skill-folders-gateway').refresh(r,data)
    r.private(work/'RECOVERED_BEFORE_SWITCH',{'manifest':data['manifest']})
    return 'ORIGINAL_API_RECOVERED_NATIVE_COMPATIBLE_READER_RETAINED'

def rollback(work,r,p,state,imports_idle):
    data,_ = state(work,tested=True,release=True)
    r.require((work/'API_SWITCH_STARTED').exists(),'Use recover-before-switch')
    live = r.inspect()
    r.require(live['Image'] in (data['image'],data['oldImage']),'Unrelated API image')
    imports_idle()
    r.worker('idle')
    if live['State']['Running']:
        r.run('docker','stop','--time','-1',r.API,timeout=60)
    r.require(not r.inspect()['State']['Running'],'API stop unconfirmed')
    try:
        imports_idle()
        r.worker('idle')
    except BaseException:
        r.run('docker','start',r.API)
        r.helper('skill-folders-gateway').refresh(r,data)
        raise
    stop_publisher(data,r,p)
    # Old reader cannot consume new metadata/empty catalogs: rollback is allowed only before user changes.
    r.require(r.b.tree(Path(p.SKILL_ROOT))==data['protected']['skills'],'Skill catalog changed; retain new image, repair forward')
    r.require(r.hashes(data['oldImage']) == {n:v['baseline'] for n,v in data['patch'].items()},'Old image drift')
    r.a.compose(data['compose'],'up','-d','--no-deps','--no-build','api')
    old = r.inspect()
    r.require(old['Image']==data['oldImage'] and old['State']['Running'],'Old API not restored')
    r.a.check_live_config(old,json.loads(r.a.compose(data['compose'],'config','--format','json')))
    if (work/'frontend-backup/COMPLETE.json').exists():
        r.helper('sku-frontend').rollback(r.a.APP,work/'frontend-backup')
    r.helper('image-cache-runtime').readiness('http://127.0.0.1:18018/api/overseas/v1/health/ready')
    r.helper('skill-folders-gateway').refresh(r,data)
    r.private(work/'ROLLED_BACK',{'manifest':data['manifest'],'image':data['oldImage']})
    return 'OLD_API_FRONTEND_RESTORED_COMPATIBLE_NATIVE_READER_RETAINED_NO_DB_REWIND'

