"""Package only reviewed committed native source, pure tests and release helpers."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

spec = importlib.util.spec_from_file_location('reuse',Path(__file__).with_name('skill-reuse-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.r


def build(repo, baseline_path, candidate=False):
    common = p.load('package-delivery')
    git = lambda *args: common.git(repo,*args)
    def clean():
        r.require(not git('diff','HEAD','--name-only').strip() and
                  not git('ls-files','--others','--exclude-standard').strip(), 'Commit release sources first')
    identity = lambda: json.loads(subprocess.check_output(
        [sys.executable,'.codex/hooks/harness.py','review-status'],cwd=repo))
    clean()
    approved = identity() if candidate else common.reviewed_status(repo)
    r.require(approved.get('currentId'), 'Prepare review snapshot first')
    commit = git('rev-parse','HEAD').decode().strip()
    baseline = json.loads(baseline_path.read_text(encoding='utf-8-sig'))
    r.native_baselines(baseline['native'])
    files = {}
    def source(name):
        path = repo/name
        r.require(not any(p.is_symlink() for p in (path,*path.parents)), 'Linked source')
        raw = common.normalized(git('show',commit+':'+name))
        r.require(raw == common.normalized(path.read_bytes()), 'Source drift')
        common.privacy_check(name,raw)
        return raw
    for name in sorted(r.NATIVE_FILES):
        files['native/'+name] = source('hengxin-smart-image/backend/'+name)
    tests = p.load('sku-package')
    tests.r.TESTS = p.TESTS
    files.update(tests.collect_tests(repo/'hengxin-smart-image/backend/tests',
        lambda name: source('hengxin-smart-image/backend/tests/'+name)))
    for name in p.HELPERS:
        key = 'scripts/release/'+name+'.py'
        files[key] = source(key)
    release = 'skill-reuse-20261106-'+('candidate-' if candidate else '')+commit[:7]
    manifest = dict(kind='skill-reuse-native-only',release=release,commit=commit,
        candidateId=approved['currentId'],mode='candidate' if candidate else 'release',
        native=baseline['native'],baseline=baseline,baselineEvidenceSha256=r.digest(baseline_path),
        files={n:hashlib.sha256(raw).hexdigest() for n,raw in sorted(files.items())})
    files['release.json'] = json.dumps(manifest,indent=2).encode()
    archive = p.load('package-text').archive_bytes(files)
    clean()
    r.require(git('rev-parse','HEAD').decode().strip() == commit and
              identity()['currentId'] == approved['currentId'], 'Review/commit changed')
    target = repo/'output/release'/release
    target.mkdir(parents=True,exist_ok=False)
    (target/'release.tar.gz').write_bytes(archive)
    audit = dict(release=release,commit=commit,candidateId=approved['currentId'],
        sha256=hashlib.sha256(archive).hexdigest(),bytes=len(archive),privacy='PASS',nativeOnly=True)
    (target/'package-audit.json').write_text(json.dumps(audit,indent=2))
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',action='store_true')
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[2],args.baseline,args.candidate)))
