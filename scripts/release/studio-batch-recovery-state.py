"""Durable native rollback phases with strict resource guards and resumable stops."""
import json
from pathlib import Path
import time

MARKER = 'NATIVE_RECOVERY.json'


def begin(work, data, r, native):
    if (work/MARKER).exists():
        guard(work,data,r,native)
        return
    proof = dict(manifest=data['manifest'],phase='stopping',
        pids={unit:native.pid(unit) for unit in r.UNITS},
        sources={unit:{name:r.digest(Path(data['protected']['units'][unit]['cwd'])/name)
                      for name in r.NATIVE_FILES} for unit in r.UNITS})
    r.private(work/MARKER,proof)
    guard(work,data,r,native)


def guard(work, data, r, native):
    proof = json.loads((work/MARKER).read_text())
    r.require(proof['manifest'] == data['manifest'] and proof['phase'] in ('stopping','restoring') and
              set(proof['pids']) == set(r.UNITS) and set(proof['sources']) == set(r.UNITS),
              'Native recovery proof drift')
    for unit,saved in data['protected']['units'].items():
        r.require(all(r.digest(p) == h for p,h in saved['files'].items()), 'Native configuration drift')
        current = r.b.tree(Path(saved['cwd'])/'app')
        expected = dict(saved['source'])
        pid = native.pid(unit)
        if unit in r.UNITS:
            r.require(isinstance(proof['pids'][unit],int) and proof['pids'][unit] >= 0 and
                      set(proof['sources'][unit]) == set(r.NATIVE_FILES), 'Native recovery identity drift')
            allowed_pids = (0,proof['pids'][unit]) if proof['phase'] == 'stopping' else (0,)
            r.require(pid in allowed_pids, 'Unexpected native restart during recovery')
            for name in r.NATIVE_FILES:
                old, new = data['native']['units'][unit]['files'][name],data['patch'][name]['sha256']
                initial = proof['sources'][unit][name]
                r.require(initial in (old,new), 'Native recovery source proof drift')
                short = name.removeprefix('app/')
                allowed = (initial,) if proof['phase'] == 'stopping' else (old,new)
                r.require(current.get(short) in allowed, 'Native recovery source drift')
                expected[short] = current[short]
            drop = native.drop_path(unit)
            if drop.exists():
                r.require(native.safe(drop).read_text() == native.DROP_CONTENT, 'Stop protection drift')
        else:
            r.require(pid == saved['pid'], 'Unrelated native PID drift')
        r.require(current == expected, 'Native source drift')


def restoring(work, data, r, native):
    native.stopped()
    guard(work,data,r,native)
    proof = json.loads((work/MARKER).read_text())
    proof['phase'] = 'restoring'
    r.private(work/MARKER,proof)


def finish(work, data, r, native):
    guard(work,data,r,native)
    r.require(all(r.digest(Path(data['protected']['units'][unit]['cwd'])/name) == digest
        for unit in r.UNITS for name,digest in data['native']['units'][unit]['files'].items()),
        'Native rollback incomplete')
    (work/MARKER).replace(work/(MARKER+'.restored'))


def stop(work, data, r, native):
    node = json.loads((work/'gate.json').read_text())['node']
    if native.pid(r.UNITS[0]) > 0:
        r.worker('paused',node)
    r.private(work/'NATIVE_STOP_STARTED',{'manifest':data['manifest']})
    for unit in r.UNITS:
        drop = native.safe(native.drop_path(unit))
        if drop.exists():
            r.require(drop.read_text() == native.DROP_CONTENT, 'Stop protection drift')
        else:
            drop.parent.mkdir(parents=True,exist_ok=True)
            with drop.open('x') as stream:
                stream.write(native.DROP_CONTENT)
            drop.chmod(0o644)
    r.run('systemctl','daemon-reload')
    for unit in r.UNITS:
        r.require(r.run('systemctl','show',unit,'-p','SendSIGKILL','--value') == 'no', 'Unsafe stop escalation')
        r.require(r.run('systemctl','show',unit,'-p','TimeoutStopUSec','--value') == 'infinity', 'Unsafe stop timeout')
    deadline = time.monotonic()+60
    for unit in reversed(r.UNITS):
        remaining = deadline-time.monotonic()
        r.require(remaining > 0,'Native stop deadline exceeded')
        if unit == r.UNITS[0] and native.pid(unit,timeout=min(4,remaining)) > 0:
            r.worker('paused',node,timeout=min(10,remaining))
        r.run('systemctl','stop','--no-block',unit)
        while True:
            remaining = deadline-time.monotonic()
            r.require(remaining > 0,'Graceful native stop pending; retain protection')
            status = r.run('systemctl','show',unit,'-p','ActiveState','--value',timeout=min(4,remaining))
            if status == 'inactive' and native.pid(unit,timeout=min(4,max(.1,deadline-time.monotonic()))) == 0:
                r.require(time.monotonic() <= deadline,'Native stop exceeded deadline')
                break
            time.sleep(.5)
    native.stopped()
    r.private(work/'NATIVE_STOPPED',{'manifest':data['manifest']})
