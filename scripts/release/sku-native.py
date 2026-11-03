"""Gracefully restart only the two drained overseas units with pinned source files."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import time

spec = importlib.util.spec_from_file_location('sku_runtime', Path(__file__).with_name('sku-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
DROP_CONTENT = '[Service]\nSendSIGKILL=no\nTimeoutStopSec=infinity\n'


def drop_path(unit):
    r.require(unit in r.UNITS, 'Unexpected native unit')
    return Path('/run/systemd/system')/(unit+'.d')/'zzzzzzzzzzzzzz-sku-20261103.conf'


def safe(path):
    r.require(not any(p.is_symlink() for p in (path, *path.parents)), 'Linked native path')
    return path


def pid(unit, timeout=4):
    return int(r.run('systemctl', 'show', unit, '-p', 'MainPID', '--value', timeout=timeout))


def stopped():
    for unit in r.UNITS:
        r.require(pid(unit) == 0, 'Overseas native process still running')
        r.require(r.run('systemctl', 'show', unit, '-p', 'ActiveState', '--value') == 'inactive',
                  'Native stop has not completed')


def guard(work, data):
    for unit, saved in data['protected']['units'].items():
        r.require(all(r.digest(p) == h for p,h in saved['files'].items()), 'Native configuration drift')
        current = r.b.tree(Path(saved['cwd'])/'app')
        expected = dict(saved['source'])
        if unit in r.UNITS:
            if (work/'NATIVE_PATCH_STARTED').exists():
                for name in r.NATIVE_FILES:
                    short = name.removeprefix('app/')
                    new = data['patch'][name]['sha256']
                    r.require(current.get(short) in {expected.get(short), new}, 'Native patch drift')
                    if (work/'NATIVE_INSTALLED').exists():
                        r.require(current.get(short) == new, 'Native installation incomplete')
                    if short in current:
                        expected[short] = current[short]
            if (work/'NATIVE_STOP_STARTED').exists():
                if not (work/'NATIVE_START_STARTED').exists():
                    r.require(pid(unit) in (0,saved['pid']), 'Unexpected native restart')
                elif (work/'NATIVE_VERIFIED').exists():
                    proof = json.loads((work/'NATIVE_VERIFIED').read_text())
                    r.require(proof['manifest'] == data['manifest'] and pid(unit) == proof['pids'][unit],
                              'Restarted native PID drift')
            else:
                r.require(pid(unit) == saved['pid'], 'Native PID drift')
            drop = drop_path(unit)
            if drop.exists():
                r.require(safe(drop).read_text() == DROP_CONTENT, 'Stop protection drift')
        else:
            r.require(pid(unit) == saved['pid'], 'Unrelated native PID drift')
        r.require(current == expected, 'Native source drift')


def baseline_roots(data):
    r.native_baselines(data.get('native'))
    r.require(set(r.UNITS) <= set(data['protected']['units']), 'Overseas native units missing')
    roots = {}
    for unit in r.UNITS:
        root = data['protected']['units'][unit]['cwd']
        files = data['native']['units'][unit]['files']
        r.require(root not in roots or roots[root] == files, 'Shared native baseline conflict')
        roots[root] = files
    r.require(all(saved['cwd'] not in roots for unit,saved in data['protected']['units'].items()
                  if unit not in r.UNITS), 'Native source is shared with unrelated service')
    return roots


def preflight(data):
    baseline_roots(data)
    for unit in r.UNITS:
        saved = data['protected']['units'][unit]
        r.require(not drop_path(unit).exists(), 'Stop override already exists')
        for name in r.NATIVE_FILES:
            path = safe(Path(saved['cwd'])/name)
            r.require(not path.exists() or path.is_file(), 'Invalid native baseline file: '+name)
            actual = r.digest(path) if path.is_file() else None
            r.require(actual == data['native']['units'][unit]['files'][name], 'Native baseline source differs: '+name)
            r.require(data['protected']['units'][unit]['source'].get(name.removeprefix('app/')) == actual,
                      'Native baseline snapshot differs: '+name)


def stop(work, data):
    node = json.loads((work/'gate.json').read_text())['node']
    r.worker('paused', node)
    r.private(work/'NATIVE_STOP_STARTED', {'manifest':data['manifest']})
    for unit in r.UNITS:
        drop = safe(drop_path(unit))
        drop.parent.mkdir(parents=True, exist_ok=True)
        with drop.open('x') as stream:
            stream.write(DROP_CONTENT)
        drop.chmod(0o644)
    r.run('systemctl', 'daemon-reload')
    for unit in r.UNITS:
        r.require(r.run('systemctl','show',unit,'-p','SendSIGKILL','--value') == 'no', 'Unsafe stop escalation')
        r.require(r.run('systemctl','show',unit,'-p','TimeoutStopUSec','--value') == 'infinity', 'Unsafe stop timeout')
    # Stop maintenance before the idle executor; no DB writes remain for the dump.
    deadline = time.monotonic()+60
    for unit in reversed(r.UNITS):
        if unit == r.UNITS[0]:
            r.require(deadline > time.monotonic(), 'Native stop deadline exceeded')
            r.worker('paused',node,timeout=min(10,deadline-time.monotonic()))
        r.run('systemctl', 'stop', '--no-block', unit)
        while True:
            remaining = deadline-time.monotonic()
            r.require(remaining>0, 'Graceful native stop pending; leave stop protection in place')
            status = r.run('systemctl','show',unit,'-p','ActiveState','--value', timeout=min(4,remaining))
            if status == 'inactive' and pid(unit,timeout=min(4,max(0.1,deadline-time.monotonic()))) == 0:
                r.require(time.monotonic() <= deadline, 'Native stop exceeded deadline')
                break
            r.require(time.monotonic() < deadline, 'Graceful native stop pending; leave stop protection in place')
            time.sleep(0.5)
    stopped()
    r.private(work/'NATIVE_STOPPED', {'manifest':data['manifest']})


def remove_protection():
    for unit in r.UNITS:
        drop = safe(drop_path(unit))
        if drop.exists():
            r.require(drop.read_text() == DROP_CONTENT, 'Stop protection drift')
            drop.unlink()
    r.run('systemctl','daemon-reload')


def verified(work, data):
    r.require(json.loads((work/'NATIVE_INSTALLED').read_text()) == {'manifest':data['manifest']},
              'Native installation proof drift')
    proof = json.loads((work/'NATIVE_VERIFIED').read_text())
    r.require(proof['manifest'] == data['manifest'], 'Native restart proof drift')
    for unit in r.UNITS:
        r.require(r.native_environment(unit) == data['environment']['native'][unit], 'Native environment changed')
        r.require(pid(unit) > 0 and pid(unit) == proof['pids'][unit], 'Native verified PID drift')
        root = Path(data['protected']['units'][unit]['cwd'])
        r.require(all(r.digest(root/name) == data['patch'][name]['sha256'] for name in r.NATIVE_FILES),
                  'Native release source differs')


def start(work, data, recovery=False):
    if recovery:
        for unit in r.UNITS:
            r.require(r.run('systemctl','show',unit,'-p','ActiveState','--value') in ('active','inactive'),
                      'Native stop still pending; retain protection')
            r.require(r.run('systemctl','show',unit,'-p','Job','--value') in ('', '0'),
                      'Native job still pending')
    else:
        stopped()
    r.private(work/'NATIVE_START_STARTED', {'manifest':data['manifest']})
    deadline = time.monotonic()+45
    for unit in reversed(r.UNITS):
        r.run('systemctl','start','--no-block',unit,timeout=4)
    while True:
        try:
            remaining = deadline-time.monotonic()
            r.require(remaining > 0, 'Native readiness deadline exceeded')
            if recovery:
                r.worker('resume',json.loads((work/'gate.json').read_text())['node'],timeout=min(10,remaining))
                remaining = deadline-time.monotonic()
                r.require(remaining>0,'Native readiness deadline exceeded')
            result = r.worker_probe('overseas','verify',work,timeout=min(15,remaining))
            r.require(result['node'] == json.loads((work/'gate.json').read_text())['node'], 'Worker node changed')
            r.require(time.monotonic() <= deadline, 'Native readiness exceeded deadline')
            break
        except (RuntimeError, __import__('subprocess').TimeoutExpired):
            r.require(time.monotonic() < deadline, 'Native readiness deadline exceeded')
            time.sleep(0.5)
    for unit in r.UNITS:
        r.require(pid(unit)>0 and r.run('systemctl','is-active',unit)=='active', 'Native restart failed')
        r.require((Path('/proc')/str(pid(unit))).stat().st_uid == 999, 'Native service identity changed')
        r.require(os.readlink(Path('/proc')/str(pid(unit))/'cwd') == data['protected']['units'][unit]['cwd'],
                  'Native working directory changed')
    remove_protection()
    r.private(work/'NATIVE_VERIFIED', {'manifest':data['manifest'], 'pids':{u:pid(u) for u in r.UNITS}})


def install(work, data, source):
    r.require((work/'MIGRATION_VERIFIED').is_file(), 'Migration must be verified before native install')
    r.require(not (work/'NATIVE_PATCH_STARTED').exists(), 'Inspect partial native patch; do not overwrite recovery files')
    stopped()
    baselines = baseline_roots(data)
    roots = sorted(baselines)
    records = []
    for index, root in enumerate(roots):
        for name in sorted(r.NATIVE_FILES):
            path = safe(Path(root)/name)
            baseline = baselines[root][name]
            if baseline is None:
                r.require(not path.exists() and path.parent.is_dir(), 'Unexpected new native file or missing parent')
                records.append({'path':str(path), 'backup':None, 'sha256':None})
            else:
                r.require(path.is_file(), 'Missing native baseline file')
                saved = work/'native-backup'/str(index)/name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, saved)
                r.require(r.digest(saved) == baseline, 'Native backup mismatch')
                records.append({'path':str(path), 'backup':str(saved), 'sha256':r.digest(saved)})
    r.private(work/'native-backup.json', records)
    r.private(work/'NATIVE_PATCH_STARTED', {'manifest':data['manifest']})
    for record in records:
        path = Path(record['path'])
        name = next(n for n in r.NATIVE_FILES if path.as_posix().endswith('/'+n))
        attrs = path.stat() if record['backup'] is not None else path.parent.stat()
        mode = attrs.st_mode & 0o777 if record['backup'] is not None else 0o644
        temporary = safe(path.with_name(path.name+'.sku-new'))
        with temporary.open('xb') as stream:
            stream.write((source/'api'/name).read_bytes())
        os.chown(temporary, attrs.st_uid, attrs.st_gid)
        temporary.chmod(mode)
        os.replace(temporary,path)
        r.require(r.digest(path) == data['patch'][name]['sha256'], 'Native installed hash mismatch')
    # Compile/read using the service identity at its actual installed location.
    for root in roots:
        code = 'import pathlib;'+''.join('compile(pathlib.Path('+repr(str(Path(root)/n))+
            ').read_bytes(),'+repr(n)+',"exec");' for n in sorted(r.NATIVE_FILES))
        r.run('runuser','-u','hengxin-overseas','--',root+'/.venv/bin/python','-B','-c',code)
    r.private(work/'NATIVE_INSTALLED', {'manifest':data['manifest']})
    start(work, data)
    guard(work, data)
    verified(work, data)
    return 'NATIVE_PATCH_INSTALLED_AND_GRACEFULLY_RESTARTED'
