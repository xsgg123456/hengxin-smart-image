"""Build a fresh frontend from an approved committed snapshot; ship no backend or data."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import importlib.util

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('archive_runtime', Path(__file__).with_name('archive-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def build(repo):
    common, assets = r.helper('package-delivery'), r.helper('package-overseas')
    git = lambda *args: common.git(repo, *args)
    def clean():
        r.require(not git('diff','HEAD','--name-only').strip() and
                  not git('ls-files','--others','--exclude-standard').strip(), 'Commit all release sources first')
    clean()
    approved = common.reviewed_status(repo)
    commit = git('rev-parse','HEAD').decode().strip()
    frontend = repo/'hengxin-smart-image/frontend'
    r.require(json.loads((frontend/'package.json').read_text())['version'] == r.VERSION, 'Version mismatch')
    output = repo/'output/archive-release'
    output.mkdir(parents=True, exist_ok=True)
    # Do not accept an older dist or a build racing edits in the shared worktree.
    with (output/'package-build.log').open('wb') as log:
        subprocess.run([shutil.which('pnpm.cmd') or shutil.which('pnpm') or 'pnpm','exec','vite','build'],
                       cwd=frontend, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=900)
    clean()
    r.require(common.reviewed_status(repo)['currentId'] == approved['currentId'], 'Snapshot changed during build')
    files = assets.collect_assets(frontend/'dist')
    r.verify_frontend(files)
    captured = {}
    for path in ['hengxin-smart-image/frontend/package.json', *['scripts/release/'+n+'.py' for n in r.HELPERS]]:
        r.safe(repo/path)
        raw = common.normalized((repo/path).read_bytes())
        r.require(raw == common.normalized(git('show',commit+':'+path)), 'Committed source drift')
        common.privacy_check(path, raw)
        captured[path] = raw
        files[path.removeprefix('hengxin-smart-image/')] = raw
    release = 'archive-20261103-'+commit[:7]
    manifest = dict(release=release,version=r.VERSION,baseVersion=r.BASE_VERSION,baseImage=r.BASE_IMAGE,
                    frontendOnly=True,mode='release',commit=commit,candidateId=approved['currentId'],
                    files={name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(files.items())})
    files['release.json'] = json.dumps(manifest,indent=2).encode()
    archive = r.helper('package-text').archive_bytes(files)
    clean()
    r.require(git('rev-parse','HEAD').decode().strip() == commit and
              common.reviewed_status(repo)['currentId'] == approved['currentId'], 'Source identity changed')
    r.require(all(common.normalized((repo/n).read_bytes()) == b for n,b in captured.items()), 'Source drift')
    r.require(assets.collect_assets(frontend/'dist') == {n:b for n,b in files.items() if n.startswith('frontend/dist/')},
              'Frontend changed during packaging')
    target = repo/'output/release'/release
    target.mkdir(parents=True,exist_ok=False)
    (target/'release.tar.gz').write_bytes(archive)
    audit = dict(release=release,sha256=hashlib.sha256(archive).hexdigest(),bytes=len(archive),
                 candidateId=approved['currentId'],commit=commit,privacy='PASS',frontendOnly=True)
    (target/'package-audit.json').write_text(json.dumps(audit,indent=2))
    return audit


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
