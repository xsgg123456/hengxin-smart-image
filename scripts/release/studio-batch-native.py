"""Patch only the prompt binding module used by both native units."""
import importlib.util
import json
import os
from pathlib import Path
import shutil

spec = importlib.util.spec_from_file_location('folders_runtime',Path(__file__).with_name('studio-batch-runtime.py'))
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
    records = backup_records(work, roots)
    for record in records:
        path, name = native.safe(Path(record['path'])),record['name']
        r.require(name in r.NATIVE_FILES and any(path == Path(root)/name for root in roots),'Native backup scope drift')
        r.require(r.digest(record['backup']) == record['sha256'],'Native backup drift')
        r.require(r.digest(path) in (record['sha256'],data['patch'][name]['sha256']),'Native target drift')
        info = path.stat()
        temporary = native.safe(path.with_name(path.name+'.studio-batch-new'))
        with temporary.open('xb') as stream:
            stream.write((source/'api'/name).read_bytes())
        os.chown(temporary,info.st_uid,info.st_gid)
        temporary.chmod(info.st_mode & 0o777)
        os.replace(temporary,path)
    for root in roots:
        code = 'import pathlib;'+''.join('compile(pathlib.Path('+repr(str(Path(root)/n))+').read_bytes(),'+
            repr(n)+',"exec");' for n in sorted(r.NATIVE_FILES))
        r.run('runuser','-u','hengxin-overseas','--',root+'/.venv/bin/python','-B','-c',code)
    semantic_probe(data)
    r.private(work/'NATIVE_INSTALLED',{'manifest':data['manifest']})
    native.start(work,data)
    native.guard(work,data)
    native.verified(work,data)
    return 'NATIVE_IMAGE_EDIT_PROMPT_INSTALLED'

def restore(work,data):
    """Caller must close API admission and drain/stop both units first."""
    native = r.helper('sku-native')
    native.stopped()
    roots = native.baseline_roots(data)
    if (work/'NATIVE_RECOVERY.json').exists():
        r.helper('studio-batch-recovery-state').restoring(work,data,r,native)
    for record in backup_records(work, roots):
        path, name = native.safe(Path(record['path'])),record['name']
        r.require(name in r.NATIVE_FILES and any(path == Path(root)/name for root in roots),'Native restore scope drift')
        r.require(r.digest(record['backup']) == record['sha256'],'Native backup drift')
        r.require(r.digest(path) in (record['sha256'],data['patch'][name]['sha256']),'Native target drift')
        # Keep incomplete bytes outside the guarded app tree, on the native filesystem.
        root = next(Path(root) for root in roots if path == Path(root)/name)
        temporary = native.safe(root/('.studio-batch-restore-'+name.replace('/','-')))
        if temporary.exists():
            r.require(temporary.is_file(), 'Invalid native restore temporary')
            temporary.unlink()
        info = path.stat()
        shutil.copy2(record['backup'],temporary)
        r.require(r.digest(temporary) == record['sha256'], 'Native restore copy incomplete')
        os.chown(temporary,info.st_uid,info.st_gid)
        temporary.chmod(info.st_mode & 0o777)
        with temporary.open('r+b') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary,path)
        r.require(r.digest(path) == record['sha256'],'Native restore failed')
    # Keep recovery evidence, but stop treating restored bytes as the new patch.
    for name in ('NATIVE_PATCH_STARTED','NATIVE_INSTALLED','NATIVE_VERIFIED'):
        marker = work/name
        if marker.exists():
            marker.replace(work/(name+'_RESTORED'))
    if (work/'NATIVE_RECOVERY.json').exists():
        r.helper('studio-batch-recovery-state').finish(work,data,r,native)
    native.start(work,data,recovery=True)
    verify_baseline(data)
    return 'NATIVE_BASELINE_RESTORED'


def backup_records(work, roots):
    records = json.loads((work/'native-backup.json').read_text())
    r.require(len(records) == len(roots)*len(r.NATIVE_FILES) and
              {record['path'] for record in records} ==
              {str(Path(root)/name) for root in roots for name in r.NATIVE_FILES},
              'Incomplete native backup records')
    return records


def verify_baseline(data):
    for unit in r.UNITS:
        root = Path(data['protected']['units'][unit]['cwd'])
        r.require(all(r.digest(root/name) == digest for name,digest in
            data['native']['units'][unit]['files'].items()),'Restored native bytes mismatch')
        r.require(r.native_environment(unit) == data['environment']['native'][unit],
            'Restored native environment mismatch')


def semantic_probe(data):
    """Run real installed code as the service user; do not connect or generate."""
    for root in native_roots(data):
        path = str(Path(root)/'app/overseas/studio/image_edits.py')
        code = ('import importlib.util,json; '
            's=importlib.util.spec_from_file_location("installed_image_edits",'+repr(path)+'); '
            'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
            'assert m.__file__=='+repr(path)+'; '
            'identifier="00000000-0000-0000-0000-000000000001"; '
            'p={"inputs":[{"id":identifier},{"id":"original"}],"imageEdits":['
            '{"pictureId":"original","pictureInputIndex":1,"text":"change",'
            '"references":[{"attachmentId":"upload:"+identifier,"inputIndex":0,'
            '"kind":"custom","customPurpose":"full purpose","note":"reference detail"}]}]}; '
            'text=m.prompt_edits(p,[{"path":"/reference.png"},{"path":"/original.png"}]); '
            'assert all(v in text for v in ("/reference.png","/original.png","full purpose","reference detail")); '
            'p["imageEdits"][0].pop("references"); '
            'assert "/original.png" in m.prompt_edits(p,[{"path":"/reference.png"},{"path":"/original.png"}]); '
            'print("NATIVE_REFERENCE_BINDING_OK")')
        r.require(r.run('runuser','-u','hengxin-overseas','--',root+'/.venv/bin/python','-B','-c',code)
            == 'NATIVE_REFERENCE_BINDING_OK','Installed native reference binding failed')


def native_roots(data):
    return sorted(r.helper('sku-native').baseline_roots(data))
