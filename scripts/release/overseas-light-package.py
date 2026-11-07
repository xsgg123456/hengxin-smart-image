"""Package only reviewed committed changes and audited frontend assets."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from importlib.util import module_from_spec, spec_from_file_location


def load(name):
    spec = spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scope = load('overseas-light-runtime')
r = scope.r
common = load('package-delivery')
assets = load('package-overseas')
collector = load('sku-package')
archive = load('package-text')


def asset_bytes(name, raw):
    # Shared, unhashed public SVGs retain their canonical Git line endings.
    # Hashed Vite assets must remain byte-for-byte identical to the build.
    if name.startswith('frontend/dist/') and not name.startswith('frontend/dist/assets/') and name.endswith('.svg'):
        return common.normalized(raw)
    return raw


def build_assets(repo, commit):
    """Build an extracted Git tree, never an ignored working-directory dist."""
    frontend = repo / 'hengxin-smart-image/frontend'
    # Keep the isolated project outside node_modules: Vite treats paths under
    # node_modules as dependencies and can omit application dynamic imports.
    cache = frontend / 'output/release-build'
    cache.mkdir(parents=True, exist_ok=True)
    node = shutil.which('node')
    r.require(node is not None, 'Node runtime missing')
    tar = common.git(repo, 'archive', '--format=tar', commit + ':hengxin-smart-image/frontend')
    env = {k: v for k, v in os.environ.items() if not k.startswith('VITE_') and k != 'NODE_OPTIONS'}
    with tempfile.TemporaryDirectory(prefix='overseas-light-', dir=cache) as temporary:
        isolated = Path(temporary).resolve()
        r.require(isolated.parent == cache.resolve() and isolated.name.startswith('overseas-light-'),
                  'Unexpected temporary build directory')
        with tarfile.open(fileobj=io.BytesIO(tar), mode='r:') as source:
            source.extractall(isolated, filter='data')
        log_path = repo / 'output/overseas-light-release-build.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('w', encoding='utf-8') as log:
            subprocess.run([node, str(frontend / 'node_modules/vue-tsc/bin/vue-tsc.js'), '--noEmit'],
                           cwd=isolated, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
            subprocess.run([node, str(frontend / 'node_modules/vite/bin/vite.js'), 'build'],
                           cwd=isolated, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
        dist = isolated / 'dist'
        files = {}
        for path in sorted(dist.rglob('*')):
            if not path.is_file() or 'demo-images' in path.parts:
                continue
            assets.no_symlink(path)
            name = 'frontend/dist/' + path.relative_to(dist).as_posix()
            raw = asset_bytes(name, path.read_bytes())
            assets.audit_asset(name, raw, frontend / 'node_modules/pdfjs-dist')
            files[name] = raw
        r.require('frontend/dist/index.html' in files, 'Isolated build did not produce index.html')
        return files


def build(repo):
    git = lambda *args: common.git(repo, *args)
    r.require(not git('status', '--porcelain', '--untracked-files=no').strip(), 'Commit reviewed sources first')
    r.require(not git('ls-files', '--others', '--exclude-standard').strip(), 'Untracked sources remain')
    approved = common.reviewed_status(repo)
    commit = git('rev-parse', 'HEAD').decode().strip()
    git('merge-base', '--is-ancestor', scope.BASE_COMMIT, commit)

    def source(name):
        raw = common.normalized(git('show', commit + ':' + name))
        r.require(raw == common.normalized((repo / name).read_bytes()), 'Committed source drift: ' + name)
        common.privacy_check(name, raw)
        return raw

    files, patch = {}, {}
    for name in sorted(r.FILES):
        path = 'hengxin-smart-image/backend/' + name
        raw = source(path)
        old = common.normalized(git('show', scope.BASE_COMMIT + ':' + path))
        files['api/' + name] = raw
        patch[name] = {'baseline': hashlib.sha256(old).hexdigest(), 'sha256': hashlib.sha256(raw).hexdigest()}
    collector.r.TESTS = scope.TESTS
    tests = repo / 'hengxin-smart-image/backend/tests'
    files.update(collector.collect_tests(tests, lambda n: source('hengxin-smart-image/backend/tests/' + n)))
    for name in scope.HELPERS:
        path = 'scripts/release/' + name + '.py'
        files[path] = source(path)
    files.update(build_assets(repo, commit))
    files['frontend/package.json'] = source('hengxin-smart-image/frontend/package.json')
    release = 'overseas-light-20261107-' + commit[:7]
    manifest = dict(release=release, version=r.VERSION, commit=commit, candidateId=approved['currentId'],
        api={'image': scope.BASE_IMAGE, 'files': patch},
        files={name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())})
    files['release.json'] = json.dumps(manifest, indent=2).encode()
    raw = archive.archive_bytes(files)
    r.require(git('rev-parse', 'HEAD').decode().strip() == commit and
              common.reviewed_status(repo)['currentId'] == approved['currentId'], 'Review identity drift')
    r.require(not git('status', '--porcelain', '--untracked-files=no').strip(), 'Source changed while packaging')
    target = repo / 'output/release' / release
    target.mkdir(parents=True, exist_ok=False)
    (target / 'release.tar.gz').write_bytes(raw)
    audit = dict(release=release, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), privacy='PASS')
    (target / 'package-audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    return audit


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
