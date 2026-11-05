"""Build production assets from an isolated fixed Git tree, never workspace dist."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
import uuid
import time
from contextlib import contextmanager

PREFIX = 'hengxin-smart-image/frontend/'


@contextmanager
def build_directory():
    parent = Path(tempfile.gettempdir()).resolve()
    root = Path(tempfile.mkdtemp(prefix='studio-batch-build-',dir=parent)).resolve()
    try:
        yield root
    finally:
        if root.parent != parent or not root.name.startswith('studio-batch-build-') or root.is_symlink():
            raise RuntimeError('Unsafe build cleanup target: '+str(root))
        # pnpm's nested dependency paths can exceed Windows MAX_PATH.
        target = '\\\\?\\'+str(root) if os.name == 'nt' else root
        for attempt in range(5):
            try:
                shutil.rmtree(target)
                break
            except FileNotFoundError:
                if not root.exists():
                    break
                if attempt == 4:
                    raise RuntimeError('Build cleanup failed; preserved path: '+str(root))
                time.sleep(.5)
            except OSError:
                if attempt == 4:
                    raise RuntimeError('Build cleanup failed; preserved path: '+str(root))
                time.sleep(.5)


def build(repo, commit, r):
    git = r.helper('package-delivery').git
    archive = git(repo,'archive','--format=zip',commit,PREFIX.rstrip('/'))
    env = {k:v for k,v in os.environ.items() if k.upper() in {
        'PATH','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','APPDATA','LOCALAPPDATA',
        'USERPROFILE','HOME','TEMP','TMP','PNPM_HOME','SYSTEMDRIVE'}}
    env.update(CI='true', NODE_ENV='production', TZ='UTC')
    pnpm = shutil.which('pnpm.cmd' if os.name == 'nt' else 'pnpm')
    r.require(pnpm is not None, 'Pinned pnpm is required')
    log = bytearray()
    log_path = repo/'output/release'/('studio-batch-build-'+uuid.uuid4().hex+'.log')
    log_path.parent.mkdir(parents=True,exist_ok=True)
    with build_directory() as temporary:
        root = Path(temporary)
        captured = {}
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            for member in source.infolist():
                name = member.filename
                r.require(not name.startswith('/') and '\\' not in name and '..' not in Path(name).parts,
                          'Unsafe Git export path')
                if member.is_dir():
                    continue
                r.require(name.startswith(PREFIX) and (member.external_attr >> 16) & 0o170000 != 0o120000,
                          'Linked or unexpected build source')
                raw = source.read(member)
                path = root/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(raw)
                captured[name] = raw
        frontend = root/PREFIX
        r.require(not (frontend/'dist').exists(), 'Tracked dist cannot be a build source')
        package = json.loads((frontend/'package.json').read_text())
        lock = (frontend/'pnpm-lock.yaml').read_bytes()
        def run(*args):
            result = subprocess.run(args,cwd=frontend,env=env,stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,timeout=1200,check=False)
            log.extend(result.stdout)
            log_path.write_bytes(log)
            r.require(result.returncode == 0, 'Isolated frontend command failed: '+args[0]+' '+args[1]+
                      '\n'+result.stdout.decode(errors='replace')[-4000:])
            return result.stdout.decode().strip()
        r.require(run('node','--version').splitlines()[-1] == 'v'+package['engines']['node'],
                  'Node version mismatch; log: '+str(log_path))
        r.require(run(pnpm,'--version').splitlines()[-1] == package['engines']['pnpm'],
                  'pnpm version mismatch; log: '+str(log_path))
        # Explicitly install dev dependencies because the production script typechecks and bundles.
        run(pnpm,'install','--frozen-lockfile','--prefer-offline','--prod=false')
        run(pnpm,'run','build')
        changed = [name for name,raw in captured.items() if (root/name).read_bytes() != raw]
        r.require(not changed, 'Fixed build source changed during build: '+', '.join(changed))
        collector = r.helper('package-overseas')
        assets = collector.collect_assets(frontend/'dist')
        r.verify_frontend(assets['frontend/dist/index.html'].decode(),assets)
        r.require(collector.collect_assets(frontend/'dist') == assets, 'Frontend build changed during packaging')
        proof = dict(commit=commit,lockSha256=hashlib.sha256(lock).hexdigest(),
            sourceTree=git(repo,'rev-parse',commit+':'+PREFIX.rstrip('/')).decode().strip(),
            command='pnpm install --frozen-lockfile --prefer-offline --prod=false && pnpm run build',
            node=package['engines']['node'],pnpm=package['engines']['pnpm'],
            files={n:hashlib.sha256(raw).hexdigest() for n,raw in sorted(assets.items())})
        return assets,proof,bytes(log)
