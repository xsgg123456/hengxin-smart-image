"""Native-only release scope and adapters over existing protected stop/start tools."""
import importlib.util
import json
import os
from pathlib import Path
import re


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r = load('sku-runtime')
r.NATIVE_FILES = {'app/overseas/execution/'+n+'.py' for n in ('materials','skill_cache','skill_content')}
r.FILES = r.base.FILES = r.b.FILES = set()
TESTS = ('test_studio_skill_cache.py', 'test_studio_skill_cache_safety.py',
         'test_studio_skill_cache_linux.py', 'test_studio_skill_trigger.py', 'test_studio_persistent_mounts.py')
HELPERS = ('account-runtime','account-worker','image-cache-runtime','skill-platform-baseline',
    'skill-platform-runtime','skill-platform-worker','sku-runtime','sku-native','studio-batch-worker',
    'release-retention-state','skill-folders-gateway','studio-batch-recovery-state',
    'skill-reuse-runtime','skill-reuse-deploy',
    'skill-reuse-native','skill-reuse-gate','skill-reuse-test','skill-reuse-preserve','skill-reuse-catalog-probe')


def helper(name):
    module = load(name)
    if name.startswith('skill-reuse-') or name == 'sku-native':
        module.r = r
    return module


def worker(mode, node='-', timeout=40):
    state = r.a.worker('overseas')
    raw = (Path('/proc')/str(state['pid'])/'environ').read_bytes()
    env = dict(x.decode().split('=',1) for x in raw.split(b'\0') if x)
    env['PYTHONPATH'] = state['cwd']
    return json.loads(r.run(state['cwd']+'/.venv/bin/python','-B',
        str(Path(__file__).with_name('studio-batch-worker.py')),mode,str(state['pid']),node,
        cwd=state['cwd'],env=env,timeout=timeout))


def verify_package(source):
    manifest = json.loads((source/'release.json').read_text())
    r.require(manifest.get('kind') == 'skill-reuse-native-only' and manifest.get('mode') in ('candidate','release'),
              'Wrong release kind/mode')
    r.require(re.fullmatch('[a-f0-9]{40}',manifest.get('commit','')) and
              re.fullmatch('[a-f0-9]{64}',manifest.get('candidateId','')), 'Missing source identity')
    r.require(re.fullmatch('skill-reuse-[a-z0-9-]+',manifest.get('release','')), 'Unsafe release name')
    r.native_baselines(manifest.get('native'))
    required = {'native/'+n for n in r.NATIVE_FILES} | {'tests/'+n for n in ('conftest.py',*TESTS)} | {
        'scripts/release/'+n+'.py' for n in HELPERS}
    names = set(manifest['files'])
    r.require(required <= names, 'Incomplete release package')
    r.require({n for n in names if not n.startswith('tests/')} ==
              {n for n in required if not n.startswith('tests/')}, 'Unexpected package scope')
    for name, expected in manifest['files'].items():
        path = source/name
        r.require(not name.startswith('/') and '\\' not in name and '..' not in Path(name).parts and
            path.resolve().is_relative_to(source.resolve()) and
            not any(p.is_symlink() for p in (path,*path.parents)), 'Unsafe package path')
        r.require(path.is_file() and r.digest(path) == expected, 'Package bytes drift: '+name)
        r.require(not name.startswith('tests/') or re.fullmatch(r'tests/[A-Za-z0-9_]+\.py',name),
                  'Unexpected test content')
    paths = list(source.rglob('*'))
    r.require(not any(p.is_symlink() for p in paths), 'Linked package')
    r.require({p.relative_to(source).as_posix() for p in paths if p.is_file()} == names|{'release.json'},
              'Unmanifested package content')
    return manifest


def fingerprint(path):
    return r.digest(path) if path.is_file() else None


def guard(work, data):
    """Accept absent originals during resumable rollback, without weakening unrelated guards."""
    native = helper('sku-native')
    recovery = work/'NATIVE_RECOVERY.json'
    if not recovery.exists():
        native.guard(work,data)
        return
    proof = json.loads(recovery.read_text())
    r.require(proof['manifest'] == data['manifest'] and proof['phase'] in ('stopping','restoring'),
              'Recovery proof drift')
    for unit,saved in data['protected']['units'].items():
        r.require(all(r.digest(p) == h for p,h in saved['files'].items()), 'Unit configuration drift')
        current, expected = r.b.tree(Path(saved['cwd'])/'app'), dict(saved['source'])
        if unit not in r.UNITS:
            r.require(native.pid(unit) == saved['pid'], 'Unrelated native restart')
        else:
            allowed = (0,proof['pids'][unit]) if proof['phase'] == 'stopping' else (0,)
            r.require(native.pid(unit) in allowed, 'Unexpected recovery PID')
            for name in r.NATIVE_FILES:
                key = name.removeprefix('app/')
                old, new = data['native']['units'][unit]['files'][name], data['patch'][name]['sha256']
                initial = proof['sources'][unit][name]
                r.require(initial in (old,new), 'Recovery source proof drift')
                r.require(current.get(key) in ((initial,) if proof['phase'] == 'stopping' else (old,new)),
                          'Recovery source drift')
                if key in current:
                    expected[key] = current[key]
                else:
                    expected.pop(key,None)
            if native.drop_path(unit).exists():
                r.require(native.safe(native.drop_path(unit)).read_text() == native.DROP_CONTENT, 'Stop guard drift')
        r.require(current == expected, 'Unrelated native source drift')


r.helper, r.worker, r.verify_package = helper, worker, verify_package
