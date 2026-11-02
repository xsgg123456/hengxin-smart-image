"""Package only approved committed platform sources over the measured live image."""
import argparse
import ast
import base64
import hashlib
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('platform_runtime', Path(__file__).with_name('skill-platform-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def build(repo, baseline_path):
    common = r.helper('package-delivery')
    git = lambda *args: common.git(repo,*args)
    def clean():
        r.require(set(git('diff','HEAD','--name-only').decode().splitlines()) <= {'AGENTS.md'}, 'Commit release sources first')
        r.require(not git('ls-files','--others','--exclude-standard').strip(), 'Untracked release sources')
    clean()
    approved = common.reviewed_status(repo)
    commit = git('rev-parse','HEAD').decode().strip()
    baseline = json.loads(baseline_path.read_text(encoding='utf-8-sig'))
    r.require(set(baseline['sources']) == r.FILES and baseline['frontendVersion'] == '0.2.56', 'Unexpected baseline')
    files, patch = {}, {}
    def source(name):
        raw = common.normalized(git('show',commit+':'+name))
        r.require(raw == common.normalized((repo/name).read_bytes()), 'Source drift')
        common.privacy_check(name,raw)
        return raw
    for name in sorted(r.FILES):
        raw = source('hengxin-smart-image/backend/'+name)
        old = base64.b64decode(baseline['sources'][name]) if baseline['sources'][name] is not None else None
        files['api/'+name] = raw
        patch[name] = dict(baseline=hashlib.sha256(old).hexdigest() if old is not None else None,
                           sha256=hashlib.sha256(raw).hexdigest())
    pending = ['conftest.py',*r.TESTS]
    seen = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        raw = source('hengxin-smart-image/backend/tests/'+name)
        files['tests/'+name] = raw
        for node in ast.walk(ast.parse(raw)):
            imports = [node.module] if isinstance(node,ast.ImportFrom) else [v.name for v in node.names] if isinstance(node,ast.Import) else []
            for module in imports:
                if module and '.' not in module and (repo/'hengxin-smart-image/backend/tests'/(module+'.py')).is_file():
                    pending.append(module+'.py')
    files['frontend/preview-skill-platforms/seed.json'] = source('hengxin-smart-image/frontend/preview-skill-platforms/seed.json')
    helpers = ['account-runtime','account-worker','image-cache-runtime','image-cache-frontend',
               'skill-platform-baseline','skill-platform-runtime','skill-platform-worker','skill-platform-database',
               'skill-platform-deploy','skill-platform-frontend']
    for name in helpers:
        path = 'scripts/release/'+name+'.py'
        files[path] = source(path)
    files.update(r.helper('package-overseas').collect_assets(repo/'hengxin-smart-image/frontend/dist'))
    files['frontend/package.json'] = source('hengxin-smart-image/frontend/package.json')
    r.require(json.loads(files['frontend/package.json'])['version'] == r.VERSION, 'Frontend version mismatch')
    release = 'skill-platform-20261102-'+commit[:7]
    manifest = dict(release=release,version=r.VERSION,commit=commit,candidateId=approved['currentId'],
        api={'image':baseline['image'],'files':patch}, baselineEvidenceSha256=r.digest(baseline_path),
        files={n:hashlib.sha256(raw).hexdigest() for n,raw in sorted(files.items())})
    files['release.json'] = json.dumps(manifest,indent=2).encode()
    archive = r.helper('package-text').archive_bytes(files)
    clean()
    r.require(common.reviewed_status(repo)['currentId'] == approved['currentId'], 'Review changed')
    target = repo/'output/release'/release
    target.mkdir(parents=True,exist_ok=False)
    (target/'release.tar.gz').write_bytes(archive)
    audit = dict(release=release,sha256=hashlib.sha256(archive).hexdigest(),bytes=len(archive),privacy='PASS')
    (target/'package-audit.json').write_text(json.dumps(audit,indent=2))
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    print(json.dumps(build(Path(__file__).resolve().parents[2],parser.parse_args().baseline)))
