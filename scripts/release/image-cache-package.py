"""Package reviewed committed changes against the measured live overseas API baseline."""
import argparse
import ast
import base64
import hashlib
import importlib.util
import json
from pathlib import Path


def helper(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(repo, baseline_path):
    common, runtime = helper('package-delivery'), helper('image-cache-runtime')
    git = lambda *args: common.git(repo, *args)
    def clean():
        changed = set(git('diff', 'HEAD', '--name-only').decode().splitlines())
        untracked = git('ls-files', '--others', '--exclude-standard').decode().splitlines()
        runtime.require(changed <= {'AGENTS.md'} and not untracked, 'Commit release sources first')
    clean()
    approved = common.reviewed_status(repo)
    commit = git('rev-parse', 'HEAD').decode().strip()
    baseline = json.loads(baseline_path.read_text(encoding='utf-8-sig'))
    runtime.require(set(baseline['sources']) == runtime.FILES, 'Unexpected production baseline scope')
    release = 'image-cache-20261030-' + commit[:7]
    files, patch = {}, {}
    def source(name):
        path = repo / name
        runtime.require(path.is_file() and not path.is_symlink(), 'Source missing or linked: ' + name)
        raw = common.normalized(git('show', commit + ':' + name))
        runtime.require(raw == common.normalized(path.read_bytes()), 'Source differs from commit')
        common.privacy_check(name, raw)
        return raw
    for name in sorted(runtime.FILES):
        raw = source('hengxin-smart-image/backend/' + name)
        old = base64.b64decode(baseline['sources'][name]) if baseline['sources'][name] is not None else None
        files['api/' + name] = raw
        patch[name] = dict(baseline=hashlib.sha256(old).hexdigest() if old is not None else None,
                           sha256=hashlib.sha256(raw).hexdigest())
    pending = ['conftest.py'] + ['test_overseas_' + n + '.py' for n in (
        'image_cache', 'thumbnail_limits', 'image_cache_settings', 'management_freeze',
        'pictures', 'pictures_protocol')] + ['test_studio_image_preview.py']
    seen = set()
    # Include the exact local fixture dependency closure, not unrelated tests or user data.
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        raw = source('hengxin-smart-image/backend/tests/' + name)
        files['tests/' + name] = raw
        for node in ast.walk(ast.parse(raw)):
            imports = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
            for module in imports:
                if module and '.' not in module and (repo / 'hengxin-smart-image/backend/tests' / (module + '.py')).is_file():
                    pending.append(module + '.py')
    for name in ('image-cache-runtime', 'image-cache-deploy', 'image-cache-frontend',
                 'account-runtime', 'account-worker'):
        path = 'scripts/release/' + name + '.py'
        files[path] = source(path)
    files.update(helper('package-overseas').collect_assets(repo / 'hengxin-smart-image/frontend/dist'))
    package = source('hengxin-smart-image/frontend/package.json')
    runtime.require(json.loads(package)['version'] == '0.2.55', 'Wrong frontend version')
    files['frontend/package.json'] = package
    manifest = dict(release=release, version='0.2.55', commit=commit, candidateId=approved['currentId'],
                    api={'image':baseline['image'], 'files':patch},
                    baselineEvidenceSha256=hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
                    files={n:hashlib.sha256(b).hexdigest() for n,b in sorted(files.items())})
    files['release.json'] = json.dumps(manifest, indent=2).encode()
    archive = helper('package-text').archive_bytes(files)
    clean()
    runtime.require(common.reviewed_status(repo)['currentId'] == approved['currentId'], 'Review changed')
    target = repo / 'output/release' / release
    target.mkdir(parents=True, exist_ok=False)
    (target / 'release.tar.gz').write_bytes(archive)
    audit = dict(release=release, files=len(files), bytes=len(archive), sha256=hashlib.sha256(archive).hexdigest(),
                 privacy='PASS', candidateId=approved['currentId'])
    (target / 'package-audit.json').write_text(json.dumps(audit, indent=2))
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[2], args.baseline)))
