"""Resumable exact-file install/restore, including absent originals; retain all old bytes."""
import json
import os
from pathlib import Path
import shutil

r = None


def fingerprint(path):
    r.helper('sku-native').safe(path)
    r.require(not path.exists() or path.is_file(), 'Invalid native source type')
    return r.digest(path) if path.exists() else None


def records(work,data):
    roots = r.helper('sku-native').baseline_roots(data)
    result = json.loads((work/'native-backup.json').read_text())
    expected = {str(Path(root)/name):(root,name,digest) for root,files in roots.items() for name,digest in files.items()}
    r.require(len(result) == len(expected) and {v['path'] for v in result} == set(expected), 'Incomplete backup scope')
    for row in result:
        root,name,digest = expected[row['path']]
        r.require(row['root'] == root and row['name'] == name and row['sha256'] == digest, 'Backup baseline drift')
        if digest is None:
            r.require(row['backup'] is None, 'Absent backup drift')
        else:
            saved = Path(row['backup'])
            r.require(saved.resolve().is_relative_to((work/'native-backup').resolve()) and
                      fingerprint(saved) == digest, 'Native backup bytes drift')
    return result


def backup(work,data):
    r.require(not (work/'native-backup.json').exists(), 'Original backup already exists')
    result = []
    for index,(root,files) in enumerate(sorted(r.helper('sku-native').baseline_roots(data).items())):
        for name,digest in sorted(files.items()):
            path = Path(root)/name
            r.require(fingerprint(path) == digest and path.parent.is_dir(), 'Native baseline drift')
            info = path.stat() if digest else path.parent.stat()
            saved = work/'native-backup'/str(index)/name if digest else None
            if saved:
                saved.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,saved)
                r.require(fingerprint(saved) == digest, 'Backup failed')
            result.append(dict(root=root,name=name,path=str(path),backup=str(saved) if saved else None,
                sha256=digest,uid=info.st_uid,gid=info.st_gid,mode=info.st_mode & 0o777 if digest else 0o644))
    r.private(work/'native-backup.json',result)


def atomic(row,raw,expected):
    native = r.helper('sku-native')
    path = native.safe(Path(row['path']))
    temporary = native.safe(Path(row['root'])/('.skill-reuse-stage-'+row['name'].replace('/','-')))
    # A crash may leave a partial stage, outside app/ and never imported. Keep it for inspection.
    if temporary.exists():
        r.require(temporary.is_file(), 'Invalid staging file')
        temporary.rename(temporary.with_name(temporary.name+'.interrupted-'+__import__('uuid').uuid4().hex))
    with temporary.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    r.require(r.digest(temporary) == expected, 'Staging hash mismatch')
    os.chown(temporary,row['uid'],row['gid'])
    temporary.chmod(row['mode'])
    os.replace(temporary,path)
    fd = os.open(path.parent,os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def install(work,data,source):
    native = r.helper('sku-native')
    native.stopped()
    r.helper('skill-reuse-gate').require_closed(work,data)
    if not (work/'NATIVE_PATCH_STARTED').exists():
        if not (work/'native-backup.json').exists():
            backup(work,data)
        records(work,data)
        r.private(work/'NATIVE_PATCH_STARTED',{'manifest':data['manifest']})
    for row in records(work,data):
        wanted = data['patch'][row['name']]['sha256']
        actual = fingerprint(Path(row['path']))
        r.require(actual in (row['sha256'],wanted), 'Native installation drift')
        if actual != wanted:
            atomic(row,(source/'native'/row['name']).read_bytes(),wanted)
    r.private(work/'NATIVE_INSTALLED',{'manifest':data['manifest']})
    r.helper('skill-reuse-test').installed(work,data,source)
    r.helper('skill-reuse-preserve').verify(work,data)
    native.start(work,data)
    native.verified(work,data)


def restore(work,data):
    native = r.helper('sku-native')
    marker = work/'NATIVE_RECOVERY.json'
    if not marker.exists():
        r.private(marker,dict(manifest=data['manifest'],phase='stopping',
            pids={u:native.pid(u) for u in r.UNITS},
            sources={u:{n:fingerprint(Path(data['protected']['units'][u]['cwd'])/n)
                for n in r.NATIVE_FILES} for u in r.UNITS}))
    runtime = r.helper('skill-reuse-runtime')
    runtime.guard(work,data)
    if any(native.pid(u) for u in r.UNITS):
        node = json.loads((work/'gate.json').read_text())['node']
        if native.pid(r.UNITS[0]):
            status = r.worker('status',node)
            r.worker('paused' if status['paused'] else 'idle',node)
            if not status['paused']:
                r.worker('pause',node)
        r.helper('studio-batch-recovery-state').stop(work,data,r,native)
    native.stopped()
    preserve = work/'recovery-preserve'
    if not preserve.exists():
        preserve.mkdir(mode=0o700)
    if not (preserve/'CONVERSATION_BASELINE').exists():
        r.helper('skill-reuse-preserve').capture(preserve,data)
    proof = json.loads(marker.read_text())
    proof['phase'] = 'restoring'
    r.private(marker,proof)
    for row in records(work,data):
        path = Path(row['path'])
        actual = fingerprint(path)
        r.require(actual in (row['sha256'],data['patch'][row['name']]['sha256']), 'Native restore drift')
        if actual == row['sha256']:
            continue
        if row['sha256'] is None:
            # Only newly introduced source leaves app/. No session/cache/old file is deleted.
            retired = native.safe(Path(row['root'])/('.skill-reuse-retired-'+row['name'].replace('/','-')))
            r.require(not retired.exists(), 'Retired source already exists; inspect')
            path.rename(retired)
        else:
            atomic(row,Path(row['backup']).read_bytes(),row['sha256'])
    runtime.guard(work,data)
    for row in records(work,data):
        r.require(fingerprint(Path(row['path'])) == row['sha256'], 'Restore incomplete')
    for name in ('NATIVE_PATCH_STARTED','NATIVE_INSTALLED','NATIVE_VERIFIED'):
        if (work/name).exists():
            (work/name).replace(work/(name+'_RESTORED'))
    marker.replace(work/'NATIVE_RECOVERY_RESTORED.json')
    native.start(work,data,recovery=True)
    verify_baseline(data)


def verify_baseline(data):
    for unit in r.UNITS:
        for name,digest in data['native']['units'][unit]['files'].items():
            r.require(fingerprint(Path(data['protected']['units'][unit]['cwd'])/name) == digest,
                      'Restored native source differs')
        r.require(r.native_environment(unit) == data['environment']['native'][unit], 'Native environment drift')
