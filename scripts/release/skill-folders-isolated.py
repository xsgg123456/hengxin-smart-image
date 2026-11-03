"""Create development-only Linux test context; never carries production configuration."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

spec = importlib.util.spec_from_file_location('folders_runtime',Path(__file__).with_name('skill-folders-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.r

def build(repo):
    backend = repo/'hengxin-smart-image/backend'
    files = {name:(backend/name).read_bytes() for name in r.FILES}
    files.update({'tests/'+path.name:path.read_bytes() for path in (backend/'tests').glob('*.py')})
    files['Dockerfile'] = ('FROM hengxin-skill-folders-test-base:44376948ece1\n'+''.join('COPY '+name+' /app/'+name+'\n' for name in sorted(r.FILES))+
        'COPY tests /tests\n').encode()
    identity = hashlib.sha256(json.dumps({n:hashlib.sha256(v).hexdigest() for n,v in sorted(files.items())},
                                       sort_keys=True).encode()).hexdigest()[:16]
    target = repo/'output/skill-folders-release'/('isolated-'+identity+'.tar.gz')
    with tarfile.open(target,'w:gz') as archive:
        for name,raw in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size,info.mode = len(raw),0o644
            archive.addfile(info,io.BytesIO(raw))
    return {'identity':identity,'archive':str(target),'image':'hengxin-skill-folders-test:'+identity,
            'testOnly':True,'files':len(files)}

if __name__=='__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
