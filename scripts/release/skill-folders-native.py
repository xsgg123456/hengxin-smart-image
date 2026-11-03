"""Only patch the shared catalog/tree readers; retain every unrelated native byte."""
import importlib.util
import json
import os
from pathlib import Path
import shutil

spec = importlib.util.spec_from_file_location('folders_runtime',Path(__file__).with_name('skill-folders-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.r

def install(work,data,source):
    native = r.helper('sku-native')
    native.stopped()
    r.helper('polling-database').backup_verified(work,data)
    roots = native.baseline_roots(data)
    if not (work/'NATIVE_PATCH_STARTED').exists():
        records = []
        for index,root in enumerate(sorted(roots)):
            for name in sorted(r.NATIVE_FILES):
                path = native.safe(Path(root)/name)
                baseline = roots[root][name]
                r.require(baseline is not None and r.digest(path) == baseline,'Native baseline drift')
                saved = work/'native-backup'/str(index)/name
                saved.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,saved)
                r.require(r.digest(saved) == baseline,'Native backup mismatch')
                records.append(dict(path=str(path),backup=str(saved),sha256=baseline,name=name))
        r.private(work/'native-backup.json',records)
        r.private(work/'NATIVE_PATCH_STARTED',{'manifest':data['manifest']})
    records = json.loads((work/'native-backup.json').read_text())
    for record in records:
        path, name = native.safe(Path(record['path'])),record['name']
        r.require(name in r.NATIVE_FILES and str(path.parent.parent.parent.parent) in roots,'Native backup scope drift')
        r.require(r.digest(record['backup']) == record['sha256'],'Native backup drift')
        r.require(r.digest(path) in (record['sha256'],data['patch'][name]['sha256']),'Native target drift')
        info = path.stat()
        temporary = native.safe(path.with_name(path.name+'.skill-folders-new'))
        with temporary.open('xb') as stream:
            stream.write((source/'api'/name).read_bytes())
        os.chown(temporary,info.st_uid,info.st_gid)
        temporary.chmod(info.st_mode & 0o777)
        os.replace(temporary,path)
    for root in roots:
        code = 'import pathlib;'+''.join('compile(pathlib.Path('+repr(str(Path(root)/n))+').read_bytes(),'+
            repr(n)+',"exec");' for n in sorted(r.NATIVE_FILES))
        r.run('runuser','-u','hengxin-overseas','--',root+'/.venv/bin/python','-B','-c',code)
    r.private(work/'NATIVE_INSTALLED',{'manifest':data['manifest']})
    native.start(work,data)
    native.guard(work,data)
    native.verified(work,data)
    return 'NATIVE_CATALOG_ONLY_INSTALLED'

def restore(work,data):
    """Caller must close API admission and drain/stop both units first."""
    native = r.helper('sku-native')
    native.stopped()
    roots = native.baseline_roots(data)
    for record in json.loads((work/'native-backup.json').read_text()):
        path, name = native.safe(Path(record['path'])),record['name']
        r.require(name in r.NATIVE_FILES and any(path == Path(root)/name for root in roots),'Native restore scope drift')
        r.require(r.digest(record['backup']) == record['sha256'],'Native backup drift')
        r.require(r.digest(path) in (record['sha256'],data['patch'][name]['sha256']),'Native target drift')
        shutil.copy2(record['backup'],path)
        r.require(r.digest(path) == record['sha256'],'Native restore failed')
    native.start(work,data,recovery=True)
    return 'NATIVE_BASELINE_RESTORED'
