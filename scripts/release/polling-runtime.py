"""0.2.61 API-only adapter over the proven SKU release primitives; no migration."""
import importlib.util
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('sku_runtime', Path(__file__).with_name('sku-runtime.py'))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
r = runtime
r.VERSION, r.OLD_REVISION, r.REVISION = '0.2.61', 'overseas_0026', 'overseas_0026'
r.BASE_VERSION = '0.2.60'
r.BASE_IMAGE = 'sha256:82c9bda8995c2fc65b270b12b37056e4404cd14f05ab8cbd56fcd5eae09fa248'
r.FILES = {'app/overseas/drafts/router.py', 'app/overseas/drafts/read.py'}
r.NATIVE_FILES = set()  # Native units may drain/restart, but never receive source patches.
r.base.FILES = r.b.FILES = r.FILES
r.TESTS += ('test_overseas_draft_reads.py', 'test_overseas_draft_reads_postgres.py',
            'test_overseas_draft_races_postgres.py', 'test_overseas_draft_restart_postgres.py')
r.HELPERS = tuple(n for n in r.HELPERS if n not in ('sku-database', 'sku-environment')) + (
    'polling-runtime', 'polling-deploy', 'polling-database')
original_helper = r.helper


def helper(name):
    module = original_helper(name)
    if name in ('sku-native', 'sku-deploy', 'sku-frontend', 'polling-database'):
        module.r = r
    if name == 'sku-frontend':
        module.BASE_VERSION = r.BASE_VERSION
    return module


def verify_frontend(index, files):
    r.require('overseas-preview' not in index and not any(
        name.endswith(('overseas-preview.html', 'demo.html')) for name in files), 'Preview frontend is not production')
    refs = re.findall(r'(?:src|href)=["\']/?(assets/[^"\'?#]+)', index)
    r.require(any(ref.endswith('.js') for ref in refs), 'Production index must reference JavaScript')
    r.require(all('frontend/dist/'+ref in files for ref in refs), 'Missing frontend entry asset; wait for build to finish')


def verify_package(source):
    manifest = json.loads((source/'release.json').read_text())
    r.require(manifest['version'] == r.VERSION and set(manifest['api']['files']) == r.FILES,
              'Unexpected polling release scope')
    r.require(manifest['api']['image'] == r.BASE_IMAGE and manifest['revision'] == r.REVISION,
              'Unexpected polling baseline')
    r.require(manifest.get('mode') in ('candidate', 'release'), 'Unknown package mode')
    r.require(re.fullmatch('[a-f0-9]{40}', manifest.get('commit', '')) and
              re.fullmatch('[a-f0-9]{64}', manifest.get('candidateId', '')), 'Missing source identity')
    r.require(re.fullmatch(r'polling-[a-z0-9-]+', manifest['release']), 'Unsafe release tag')
    r.native_baselines(manifest.get('native'))
    required = {'api/'+n for n in r.FILES} | {'tests/'+n for n in ('conftest.py', *r.TESTS)} | {
        'frontend/package.json', 'frontend/dist/index.html'} | {'scripts/release/'+n+'.py' for n in r.HELPERS}
    r.require(required <= set(manifest['files']), 'Incomplete package')
    for name, expected in manifest['files'].items():
        path = source/name
        r.require(path.resolve().is_relative_to(source.resolve()) and
                  not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe package path')
        r.require(r.digest(path) == expected, 'Package checksum mismatch: '+name)
    paths = list(source.rglob('*'))
    r.require(not any(p.is_symlink() for p in paths), 'Linked package entry')
    r.require({p.relative_to(source).as_posix() for p in paths if p.is_file()} ==
              set(manifest['files']) | {'release.json'}, 'Unmanifested package content')
    r.require({n for n in manifest['files'] if n.startswith('api/')} == {'api/'+n for n in r.FILES},
              'Unexpected API content')
    r.require({n for n in manifest['files'] if n.startswith('scripts/')} ==
              {'scripts/release/'+n+'.py' for n in r.HELPERS}, 'Unexpected helper content')
    for name, patch in manifest['api']['files'].items():
        r.require((patch['baseline'] is None or re.fullmatch('[a-f0-9]{64}', patch['baseline'])) and
                  patch['sha256'] == manifest['files']['api/'+name], 'Patch checksum mismatch')
    r.require(json.loads((source/'frontend/package.json').read_text())['version'] == r.VERSION,
              'Frontend version mismatch')
    verify_frontend((source/'frontend/dist/index.html').read_text(), manifest['files'])
    return manifest


r.helper, r.verify_package, r.verify_frontend = helper, verify_package, verify_frontend
