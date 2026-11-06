"""Manifest-pinned physical Skill release; no business credentials in test processes."""
import copy
import importlib.util
import json
from pathlib import Path
import re


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reuse = load('skill-reuse-runtime')
r = reuse.r
PUBLISHER = 'hengxin-skill-publisher'
SKILL_ROOT = '/var/lib/hengxin-overseas/local-skills'
TRANSFER_ROOT = '/var/lib/hengxin-overseas/skill-transfers'
SOCKET_ROOT = '/run/hengxin-skill-publisher'
EXECUTION_ROOT = '/var/lib/hengxin-overseas/execution'
HELPERS = tuple(sorted(set(reuse.HELPERS) | {
    'skill-physical-runtime', 'skill-physical-deploy', 'skill-physical-native',
    'skill-physical-recovery', 'skill-physical-backup',
    'skill-physical-test', 'skill-physical-maintenance', 'sku-deploy', 'sku-frontend', 'polling-runtime',
    'polling-database', 'archive-runtime', 'archive-deploy'}))


def helper(name):
    module = load(name)
    if name.startswith(('skill-physical-', 'skill-reuse-')) or name in (
            'sku-native', 'sku-deploy', 'sku-frontend', 'polling-database'):
        module.r = r
    if name == 'skill-reuse-runtime':
        module.guard = lambda work, data: reuse.guard(work, data)
    if name == 'sku-frontend':
        module.BASE_VERSION = r.BASE_VERSION
    return module


def safe_name(name):
    return isinstance(name, str) and re.fullmatch(r'app/(?:[a-zA-Z_][a-zA-Z_0-9]*/)*[a-zA-Z_][a-zA-Z_0-9]*\.py', name)


def verify_package(source):
    manifest = json.loads((source/'release.json').read_text())
    r.require(manifest.get('kind') == 'skill-physical' and manifest.get('mode') in ('candidate', 'release'),
              'Wrong physical release kind/mode')
    r.require(re.fullmatch(r'skill-physical-[a-z0-9-]+', manifest.get('release', '')), 'Unsafe release name')
    r.require(re.fullmatch('[a-f0-9]{40}', manifest.get('commit', '')) and
              re.fullmatch('[a-f0-9]{64}', manifest.get('candidateId', '')), 'Missing reviewed identity')
    r.require(manifest['revision'] == 'overseas_0026', 'Unexpected schema; this release has no migration')
    r.FILES = r.base.FILES = r.b.FILES = set(manifest['api']['files'])
    r.require(r.FILES and all(safe_name(n) for n in r.FILES), 'Unsafe patch scope')
    r.NATIVE_FILES = set(manifest['native']['units'][r.UNITS[0]]['files'])
    r.require(r.NATIVE_FILES and r.NATIVE_FILES <= r.FILES, 'Native files must be API patch subset')
    r.native_baselines(manifest['native'])
    r.VERSION, r.BASE_VERSION = manifest['version'], manifest['baseline']['frontendVersion']
    r.TESTS = tuple(manifest['tests']['api'])
    r.REVISION = manifest['revision']
    r.require(set(manifest['publisher']['files']) == r.FILES, 'Publisher patch scope differs')
    for role in ('api', 'publisher'):
        r.require(re.fullmatch('sha256:[a-f0-9]{64}', manifest[role]['image']), 'Invalid baseline image')
        for name, item in manifest[role]['files'].items():
            r.require(item['baseline'] is None or re.fullmatch('[a-f0-9]{64}', item['baseline']), 'Bad baseline digest')
            r.require(item['sha256'] == manifest['files']['api/'+name], 'Patch bytes differ')
    tests = set().union(*[set(manifest['tests'][k]) for k in ('api', 'native', 'root')])
    r.require(all(manifest['tests'][k] for k in ('api', 'native', 'root')), 'Required test identity missing')
    r.require('test_skill_object_storage.py' not in manifest['tests']['api'] or
              'test_skill_object_storage.py' in manifest['tests']['root'], 'Protected publication requires real-root coverage')
    r.require(all(re.fullmatch(r'test_[a-zA-Z0-9_]+\.py', n) for n in tests), 'Unsafe test name')
    required = {'api/'+n for n in r.FILES} | {'tests/'+n for n in tests | {'conftest.py'}} | {
        'frontend/package.json', 'frontend/dist/index.html'} | {'scripts/release/'+n+'.py' for n in HELPERS}
    names = set(manifest['files'])
    r.require(required <= names, 'Incomplete physical release package')
    for name, digest in manifest['files'].items():
        path = source/name
        r.require(not name.startswith('/') and '\\' not in name and '..' not in Path(name).parts and
                  path.resolve().is_relative_to(source.resolve()) and
                  not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe package path')
        r.require(path.is_file() and r.digest(path) == digest, 'Package bytes drift: '+name)
        r.require(name in required or re.fullmatch(r'tests/[a-zA-Z0-9_]+\.py', name) or
                  name.startswith('frontend/dist/'), 'Unexpected package content')
    paths = list(source.rglob('*'))
    r.require(not any(p.is_symlink() for p in paths), 'Linked package')
    r.require({p.relative_to(source).as_posix() for p in paths if p.is_file()} == names | {'release.json'},
              'Unmanifested package bytes')
    r.require(json.loads((source/'frontend/package.json').read_text())['version'] == r.VERSION, 'Version drift')
    if manifest['mode'] == 'release':
        proof = manifest.get('frontendBuild', {})
        r.require(proof.get('commit') == manifest['commit'] and proof.get('files') == {
            name: value for name, value in manifest['files'].items() if name.startswith('frontend/dist/')},
            'Frontend must be built from this pinned commit with exact output hashes')
    load('polling-runtime').verify_frontend((source/'frontend/dist/index.html').read_text(), manifest['files'])
    return manifest


def overlay(before, images):
    """Only change images plus publisher's explicit native history bind and setting."""
    r.require('skill-publisher' in before['services'], 'Existing publisher missing from API compose chain')
    publisher = before['services']['skill-publisher']
    r.require(publisher.get('user') == '0:0', 'Publisher must remain root')
    volumes = publisher.get('volumes', [])
    r.require(not any(v['target'] == EXECUTION_ROOT for v in volumes), 'Publisher execution mount already exists')
    return {'services': {'api': {'image': images['api']}, 'skill-publisher': {
        'image': images['publisher'], 'environment': {'OVERSEAS_CODEX_EXECUTION_ROOT': EXECUTION_ROOT},
        'volumes': [{'type': 'bind', 'source': EXECUTION_ROOT, 'target': EXECUTION_ROOT, 'read_only': False}]}}}


def check_overlay(before, after, images):
    expected = copy.deepcopy(before)
    expected['services']['api']['image'] = images['api']
    publisher = expected['services']['skill-publisher']
    publisher['image'] = images['publisher']
    publisher['environment']['OVERSEAS_CODEX_EXECUTION_ROOT'] = EXECUTION_ROOT
    actual = copy.deepcopy(after)
    mounts = actual['services']['skill-publisher']['volumes']
    added = [m for m in mounts if m['target'] == EXECUTION_ROOT]
    r.require(len(added) == 1 and added[0]['type'] == 'bind' and added[0]['source'] == EXECUTION_ROOT and
              not added[0].get('read_only', False), 'Publisher native execution bind missing')
    actual['services']['skill-publisher']['volumes'] = [m for m in mounts if m['target'] != EXECUTION_ROOT]
    r.require(actual == expected, 'Unrelated Compose configuration changed')


r.helper, r.verify_package = helper, verify_package
