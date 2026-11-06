"""Standalone read-only production baseline; outputs hashes, never configuration secrets."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

FILES = {'app/overseas/execution/'+n+'.py' for n in ('materials','skill_cache','skill_content')}
UNITS = ('hengxin-overseas-worker.service','hengxin-overseas-outbox.service')


def run(*args):
    return subprocess.check_output(args,text=True,timeout=45).strip()


def snapshot():
    api = json.loads(run('docker','inspect','hengxin-overseas-api-1'))[0]
    if not api['State']['Running']:
        raise RuntimeError('API not running')
    units, roots, dependencies = {}, {}, {}
    for unit in UNITS:
        pid = int(run('systemctl','show',unit,'-p','MainPID','--value'))
        if pid <= 0:
            raise RuntimeError('Native not running')
        root = Path(os.readlink(Path('/proc')/str(pid)/'cwd'))
        roots[unit] = str(root)
        units[unit] = {'files':{n:hashlib.sha256((root/n).read_bytes()).hexdigest()
                             if (root/n).is_file() else None for n in sorted(FILES)}}
        dependency = root/'app/overseas/studio/context_fs.py'
        dependencies[unit] = hashlib.sha256(dependency.read_bytes()).hexdigest()
    return dict(native={'units':units},roots=roots,dependencies=dependencies,
        api=dict(id=api['Id'],image=api['Image'],started=api['State']['StartedAt']),
        revision=run('docker','exec','hengxin-overseas-overseas-postgres-1','psql','-U','postgres',
            '-d','hengxin_overseas','-Atc','SELECT version_num FROM overseas_alembic_version'))


if __name__ == '__main__':
    print(json.dumps(snapshot()))
