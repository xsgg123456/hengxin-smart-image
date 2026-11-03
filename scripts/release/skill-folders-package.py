"""Build a pinned test candidate or reviewed committed Skill-folder release."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

spec = importlib.util.spec_from_file_location('folders_runtime',Path(__file__).with_name('skill-folders-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.r

def build(repo,baseline_path,candidate=False):
    common = r.helper('package-delivery')
    git = lambda *args: common.git(repo,*args)
    identity = lambda: json.loads(subprocess.check_output([sys.executable,'.codex/hooks/harness.py','review-status'],cwd=repo))
    def clean():
        r.require(not git('diff','HEAD','--name-only').strip(),'Commit release sources first')
        r.require(not git('ls-files','--others','--exclude-standard').strip(),'Untracked release sources')
    if not candidate:
        clean()
    approved = identity() if candidate else common.reviewed_status(repo)
    r.require(approved.get('currentId'),'Prepare harness candidate first')
    commit = git('rev-parse','HEAD').decode().strip()
    baseline = json.loads(baseline_path.read_text(encoding='utf-8-sig'))
    r.require(set(baseline['sources']) == r.FILES and baseline['frontendVersion'] == r.BASE_VERSION and
              baseline['image'] == r.BASE_IMAGE and baseline['revision'] == r.REVISION,'Unexpected baseline')
    files, patch, captured = {}, {}, {}
    def source(name):
        path = repo/name
        r.require(not any(p.is_symlink() for p in (path,*path.parents)),'Linked source')
        raw = common.normalized(path.read_bytes())
        if not candidate:
            r.require(raw == common.normalized(git('show',commit+':'+name)),'Source drift')
        common.privacy_check(name,raw)
        captured[name] = raw
        return raw
    for name in sorted(r.FILES):
        raw = source('hengxin-smart-image/backend/'+name)
        old = baseline['sources'][name]
        files['api/'+name] = raw
        patch[name] = dict(baseline=hashlib.sha256(base64.b64decode(old,validate=True)).hexdigest()
                          if old is not None else None,sha256=hashlib.sha256(raw).hexdigest())
    native = {'units':{unit:{'files':{name:hashlib.sha256(base64.b64decode(
        baseline['nativeSources'][unit][name],validate=True)).hexdigest() for name in r.NATIVE_FILES}}
        for unit in r.UNITS}}
    r.native_baselines(native)
    package = r.helper('sku-package')
    package.r = r
    files.update(package.collect_tests(repo/'hengxin-smart-image/backend/tests',
        lambda name:source('hengxin-smart-image/backend/tests/'+name)))
    for name in r.HELPERS:
        path = 'scripts/release/'+name+'.py'
        files[path] = source(path)
    assets = r.helper('package-overseas').collect_assets(repo/'hengxin-smart-image/frontend/dist')
    r.verify_frontend(assets['frontend/dist/index.html'].decode(),assets)
    files.update(assets)
    files['frontend/package.json'] = source('hengxin-smart-image/frontend/package.json')
    r.require(json.loads(files['frontend/package.json'])['version'] == r.VERSION,'Version mismatch')
    release = 'skill-folders-20261103-'+('candidate-'+approved['currentId'][:12] if candidate else commit[:7])
    manifest = dict(release=release,version=r.VERSION,revision=r.REVISION,commit=commit,
        candidateId=approved['currentId'],mode='candidate' if candidate else 'release',
        api={'image':r.BASE_IMAGE,'files':patch},native=native,
        baselineEvidenceSha256=r.digest(baseline_path),
        files={n:hashlib.sha256(raw).hexdigest() for n,raw in sorted(files.items())})
    files['release.json'] = json.dumps(manifest,indent=2).encode()
    archive = r.helper('package-text').archive_bytes(files)
    if not candidate:
        clean()
    r.require(git('rev-parse','HEAD').decode().strip() == commit and identity()['currentId'] == approved['currentId'],
              'Source identity changed')
    r.require(all(common.normalized((repo/n).read_bytes()) == raw for n,raw in captured.items()),'Source drift')
    r.require(r.helper('package-overseas').collect_assets(repo/'hengxin-smart-image/frontend/dist') == assets,
              'Frontend build changed during packaging')
    target = repo/'output/release'/release
    target.mkdir(parents=True,exist_ok=False)
    (target/'release.tar.gz').write_bytes(archive)
    audit = dict(release=release,sha256=hashlib.sha256(archive).hexdigest(),bytes=len(archive),
                 mode=manifest['mode'],candidateId=approved['currentId'],privacy='PASS')
    (target/'package-audit.json').write_text(json.dumps(audit,indent=2))
    return audit

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',action='store_true')
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[2],args.baseline,args.candidate)))
