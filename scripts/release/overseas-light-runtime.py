"""Scope and integrity checks for the overseas API/frontend-only release."""
import importlib.util
import json
from pathlib import Path
import re


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r = load('skill-platform-runtime')
r.FILES = {'app/overseas/' + name + '.py' for name in (
    'management/facts', 'management/router', 'management/usage',
    'tasks/queries', 'tasks/router', 'archives/router', 'archives/service')}
r.VERSION = '0.2.67'
r.REVISION = 'overseas_0026'
BASE_IMAGE = 'sha256:8c9f489c3ae407332df98d725016fc12d99d55bfe76a5326f2dc5b73c0fd5c81'
BASE_COMMIT = 'b8d0b57e3dcfdcefd8bda400af672efac6b18240'
TESTS = ('test_overseas_management.py', 'test_overseas_management_operators.py', 'test_overseas_tasks.py',
         'test_overseas_archive_audit.py', 'test_overseas_lightweight.py', 'test_overseas_lightweight_postgres.py')
HELPERS = ('account-runtime', 'skill-platform-baseline', 'skill-platform-runtime', 'sku-runtime', 'sku-native',
           'skill-reuse-gate', 'sku-frontend', 'image-cache-runtime', 'overseas-light-runtime',
           'overseas-light-guard', 'overseas-light-frontend', 'overseas-light-contract', 'overseas-light-deploy')


def verify_package(source):
    manifest = json.loads((source / 'release.json').read_text())
    r.require(manifest.get('version') == r.VERSION and manifest.get('api', {}).get('image') == BASE_IMAGE,
              'Release baseline mismatch')
    r.require(re.fullmatch(r'overseas-light-20261107-[a-f0-9]{7}', manifest.get('release', '')) and
              re.fullmatch('[a-f0-9]{40}', manifest.get('commit', '')) and
              re.fullmatch('[a-f0-9]{64}', manifest.get('candidateId', '')), 'Missing reviewed identity')
    r.require(set(manifest['api']['files']) == r.FILES, 'Unexpected API files')
    names = set(manifest['files'])
    required = {'api/' + name for name in r.FILES} | {'tests/' + name for name in ('conftest.py', *TESTS)} | {
        'scripts/release/' + name + '.py' for name in HELPERS} | {'frontend/package.json', 'frontend/dist/index.html'}
    r.require(required <= names, 'Incomplete package')
    r.require({n for n in names if n.startswith('api/')} == {'api/' + n for n in r.FILES}, 'API scope drift')
    r.require({n for n in names if n.startswith('scripts/')} ==
              {'scripts/release/' + n + '.py' for n in HELPERS}, 'Helper scope drift')
    for name, expected in manifest['files'].items():
        path = source / name
        r.require(not name.startswith('/') and '\\' not in name and '..' not in Path(name).parts and
                  path.resolve().is_relative_to(source.resolve()) and
                  not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe package path')
        r.require(path.is_file() and r.digest(path) == expected, 'Package checksum mismatch: ' + name)
        if name.startswith('tests/'):
            r.require(re.fullmatch(r'tests/[A-Za-z0-9_]+\.py', name), 'Unexpected test file')
        else:
            r.require(name in required or name.startswith('frontend/dist/'), 'Unexpected package file')
    r.require({p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()} ==
              names | {'release.json'}, 'Unmanifested package files')
    r.require(json.loads((source / 'frontend/package.json').read_text())['version'] == r.VERSION,
              'Frontend version mismatch')
    entry = (source / 'frontend/dist/index.html').read_text(encoding='utf-8')
    refs = re.findall(r'(?:src|href)=["\'](/assets/[^"\'?#]+\.(?:js|css))', entry)
    r.require(any(ref.endswith('.js') for ref in refs), 'Frontend entry missing JavaScript')
    r.require(all('frontend/dist' + ref in names for ref in refs), 'Frontend entry asset missing')
    for name, hashes in manifest['api']['files'].items():
        r.require(set(hashes) == {'baseline', 'sha256'} and all(re.fullmatch('[a-f0-9]{64}', value)
                  for value in hashes.values()) and hashes['sha256'] == manifest['files']['api/' + name],
                  'API source evidence mismatch')
    return manifest


r.verify_package = verify_package
