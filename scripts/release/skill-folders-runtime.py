"""Pinned 0.2.63 Skill-folder release adapter; no business migration."""
import importlib.util
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('polling_runtime', Path(__file__).with_name('polling-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.runtime
r.VERSION, r.BASE_VERSION = '0.2.63', '0.2.62'
r.BASE_IMAGE = 'sha256:44376948ece1f3ed50fb99c8ebc7ef7fdfdbad486b714c3987c2c64c793f9067'
r.FILES = {'app/overseas/management/'+n+'.py' for n in (
    'router','installed_catalog','installed_tree','skill_transfer_schema','skill_transfer_store','skill_publisher',
    'skill_transfer_client','skill_transfer_router','skill_publication','skill_downloads')}
r.NATIVE_FILES = {'app/overseas/management/'+n+'.py' for n in ('installed_catalog','installed_tree')}
r.base.FILES = r.b.FILES = r.FILES
r.TESTS = ('test_overseas_installed_skills.py','test_overseas_installed_titles.py',
           'test_overseas_skill_transfers.py','test_overseas_skill_transfers_failures.py',
           'test_overseas_management_freeze.py')
r.HELPERS = tuple(dict.fromkeys((*r.HELPERS, 'archive-runtime','archive-deploy',
    'skill-folders-runtime','skill-folders-deploy','skill-folders-native','skill-folders-recovery',
    'skill-folders-gateway')))
original_helper = r.helper
SOCKET_ROOT = '/run/hengxin-skill-publisher'
TRANSFER_ROOT = '/var/lib/hengxin-overseas/skill-transfers'
SKILL_ROOT = '/var/lib/hengxin-overseas/local-skills'
PUBLISHER = 'hengxin-skill-publisher'

def helper(name):
    module = original_helper(name)
    if name in ('sku-native','sku-deploy','sku-frontend','polling-database','polling-deploy',
                'skill-folders-native'):
        module.r = r
    if name == 'sku-frontend':
        module.BASE_VERSION = r.BASE_VERSION
    return module

def verify_package(source):
    manifest = json.loads((source/'release.json').read_text())
    r.require(manifest['version'] == r.VERSION and set(manifest['api']['files']) == r.FILES,
              'Unexpected folder release scope')
    r.require(manifest['api']['image'] == r.BASE_IMAGE and manifest['revision'] == r.REVISION,
              'Unexpected folder baseline')
    r.require(manifest.get('mode') in ('candidate','release'), 'Unknown package mode')
    r.require(re.fullmatch('[a-f0-9]{40}', manifest.get('commit','')) and
              re.fullmatch('[a-f0-9]{64}', manifest.get('candidateId','')), 'Missing source identity')
    r.require(re.fullmatch(r'skill-folders-[a-z0-9-]+',manifest['release']), 'Unsafe release name')
    r.native_baselines(manifest.get('native'))
    required = {'api/'+n for n in r.FILES} | {'tests/'+n for n in ('conftest.py',*r.TESTS)} | {
        'frontend/package.json','frontend/dist/index.html'} | {'scripts/release/'+n+'.py' for n in r.HELPERS}
    r.require(required <= set(manifest['files']), 'Incomplete package')
    for name, expected in manifest['files'].items():
        path = source/name
        r.require(not name.startswith('/') and '\\' not in name and '..' not in Path(name).parts and
                  path.resolve().is_relative_to(source.resolve()) and
                  not any(p.is_symlink() for p in (path,*path.parents)), 'Unsafe package path')
        r.require(r.digest(path) == expected, 'Package checksum mismatch: '+name)
    paths = list(source.rglob('*'))
    r.require(not any(p.is_symlink() for p in paths), 'Linked package')
    r.require({p.relative_to(source).as_posix() for p in paths if p.is_file()} ==
              set(manifest['files'])|{'release.json'}, 'Unmanifested package content')
    r.require({n for n in manifest['files'] if n.startswith('api/')} == {'api/'+n for n in r.FILES},
              'Unexpected API content')
    r.require({n for n in manifest['files'] if n.startswith('scripts/')} ==
              {'scripts/release/'+n+'.py' for n in r.HELPERS}, 'Unexpected release helpers')
    for name, patch in manifest['api']['files'].items():
        r.require((patch['baseline'] is None or re.fullmatch('[a-f0-9]{64}',patch['baseline'])) and
                  patch['sha256'] == manifest['files']['api/'+name], 'Patch checksum mismatch')
    r.require(json.loads((source/'frontend/package.json').read_text())['version'] == r.VERSION, 'Version mismatch')
    r.verify_frontend((source/'frontend/dist/index.html').read_text(),manifest['files'])
    return manifest

r.helper, r.verify_package = helper, verify_package
