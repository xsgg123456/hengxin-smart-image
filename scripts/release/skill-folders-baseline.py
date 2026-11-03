"""Read-only baseline capture; source bytes are code only, never environment secrets."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess

FILES = {'app/overseas/management/'+name+'.py' for name in (
    'router','installed_catalog','installed_tree','skill_transfer_schema','skill_transfer_store','skill_publisher',
    'skill_transfer_client','skill_transfer_router','skill_publication','skill_downloads')}
NATIVE_FILES = {'app/overseas/management/'+name+'.py' for name in ('installed_catalog','installed_tree')}
UNITS = ('hengxin-overseas-worker.service','hengxin-overseas-outbox.service')

def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError('Read-only probe failed: '+args[0])
    return result.stdout.strip()

def snapshot():
    api = 'hengxin-overseas-api-1'
    live = json.loads(run('docker','inspect',api))[0]
    if not live['State']['Running']:
        raise RuntimeError('API not running')
    code = ('import base64,json,pathlib;print(json.dumps({n:base64.b64encode(pathlib.Path("/app",n).read_bytes()).decode() '
            'if pathlib.Path("/app",n).is_file() else None for n in '+repr(sorted(FILES))+'}))')
    sources = json.loads(run('docker','exec',api,'python','-B','-c',code))
    units, native = {}, {}
    for unit in UNITS:
        pid = int(run('systemctl','show',unit,'-p','MainPID','--value'))
        if pid <= 0:
            raise RuntimeError('Native not running')
        root = Path(os.readlink(Path('/proc')/str(pid)/'cwd'))
        units[unit] = {'pid':pid,'cwd':str(root)}
        native[unit] = {n:base64.b64encode((root/n).read_bytes()).decode() if (root/n).is_file() else None
                        for n in sorted(NATIVE_FILES)}
    root = Path('/var/lib/hengxin-overseas/local-skills')
    current = json.loads((root/'current.json').read_text())
    release = root/'releases'/current['release']
    manifest = json.loads((release/'manifest.json').read_text())
    tree = {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
    result = dict(image=live['Image'],apiId=live['Id'],sources=sources,units=units,nativeSources=native,
        revision=run('docker','exec','hengxin-overseas-overseas-postgres-1','psql','-U','postgres','-d',
                     'hengxin_overseas','-Atc','SELECT version_num FROM overseas_alembic_version'),
        frontendVersion=json.loads(Path('/opt/hengxin-smart-image/frontend/package.json').read_text())['version'],
        mounts=[{k:m.get(k) for k in ('Type','Source','Destination','RW')} for m in live['Mounts']],
        skills={'release':current['release'],'packages':len(manifest['items']),
                'files':sum(1 for p in release.rglob('*') if p.is_file() and p != release/'manifest.json'),
                'treeSha256':hashlib.sha256(json.dumps(tree,sort_keys=True).encode()).hexdigest()})
    if run('docker','inspect','--format','{{.Id}}',api) != live['Id']:
        raise RuntimeError('API changed during capture')
    return result

if __name__ == '__main__':
    print(json.dumps(snapshot()))
