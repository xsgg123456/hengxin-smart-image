"""Pinned 0.2.64 batch annotation release adapter; no business migration."""
import importlib.util
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('polling_runtime', Path(__file__).with_name('polling-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.runtime
r.VERSION, r.BASE_VERSION = '0.2.64', '0.2.63'
r.BASE_IMAGE = 'sha256:bd981ca42788da650871879f4effb376062c5090ffefa1b3824387479c4246b5'
r.FILES = {'app/overseas/studio/'+n+'.py' for n in (
    'schemas','image_edits','service','queries','image_edit_history')}
r.NATIVE_FILES = {'app/overseas/studio/image_edits.py'}
r.base.FILES = r.b.FILES = r.FILES
r.TESTS = ('test_studio_image_edits.py','test_studio_image_references.py',
    'test_studio_image_references_validation.py','test_studio_image_references_postgres.py',
    'test_studio_message_metadata.py',
    'test_studio_message_metadata_postgres.py','test_overseas_studio.py',
    'test_overseas_studio_postgres.py','test_studio_sessions.py')
r.HELPERS = tuple(dict.fromkeys((*r.HELPERS, 'archive-runtime','archive-deploy',
    'studio-batch-runtime','studio-batch-deploy','studio-batch-native','studio-batch-recovery',
    'skill-folders-gateway','studio-batch-worker','studio-batch-recovery-state')))
original_helper = r.helper


def worker(mode, node='-', timeout=40):
    state = r.a.worker('overseas')
    raw = (Path('/proc')/str(state['pid'])/'environ').read_bytes()
    env = dict(x.decode().split('=',1) for x in raw.split(b'\0') if x)
    env['PYTHONPATH'] = state['cwd']
    return json.loads(r.run(state['cwd']+'/.venv/bin/python','-B',
        str(Path(__file__).with_name('studio-batch-worker.py')),mode,str(state['pid']),node,
        cwd=state['cwd'],env=env,timeout=timeout))

def helper(name):
    module = original_helper(name)
    if name in ('sku-native','sku-deploy','sku-frontend','polling-database','polling-deploy',
                'studio-batch-native'):
        module.r = r
    if name == 'sku-frontend':
        module.BASE_VERSION = r.BASE_VERSION
    if name == 'sku-native':
        original_guard = module.guard
        module.guard = lambda work,data: (helper('studio-batch-recovery-state').guard(work,data,r,module)
            if (work/'NATIVE_RECOVERY.json').exists() else original_guard(work,data))
    return module

def verify_package(source):
    manifest = json.loads((source/'release.json').read_text())
    r.require(manifest['version'] == r.VERSION and set(manifest['api']['files']) == r.FILES,
              'Unexpected batch release scope')
    r.require(manifest['api']['image'] == r.BASE_IMAGE and manifest['revision'] == r.REVISION,
              'Unexpected batch baseline')
    r.require(manifest.get('mode') in ('candidate','release'), 'Unknown package mode')
    r.require(re.fullmatch('[a-f0-9]{40}', manifest.get('commit','')) and
              re.fullmatch('[a-f0-9]{64}', manifest.get('candidateId','')), 'Missing source identity')
    r.require(re.fullmatch(r'studio-batch-[a-z0-9-]+',manifest['release']), 'Unsafe release name')
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
    proof = manifest.get('frontendBuild', {})
    r.require(proof.get('commit') == manifest['commit'] and
              re.fullmatch('[a-f0-9]{40}', proof.get('sourceTree','')) and
              re.fullmatch('[a-f0-9]{64}', proof.get('lockSha256','')) and
              proof.get('files') == {n:h for n,h in manifest['files'].items() if n.startswith('frontend/dist/')},
              'Frontend build provenance differs from package')
    r.verify_frontend((source/'frontend/dist/index.html').read_text(),manifest['files'])
    return manifest

r.helper, r.verify_package, r.worker = helper, verify_package, worker
