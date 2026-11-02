"""Add one complete OUTON package without changing existing packages or database state."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True

NAME = 'amazon-outon-image-brief-to-prompts'
ROOT = Path('/var/lib/hengxin-overseas/local-skills')


def helper(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def merged_manifest(previous, package, entries):
    if any(item['name'] == NAME for item in previous['items']):
        raise ValueError('Skill already installed; inspect before replacing')
    if package.name != NAME:
        raise ValueError('Unexpected Skill identity')
    item = dict(name=NAME, displayName='Amazon OUTON 图需转正式生图任务',
                description=package.description, checksum=package.checksum, entries=entries,
                source=NAME, sourceName=NAME, sourceChecksum=package.checksum,
                sourceEntries=entries, adaptedFiles=[])
    return dict(schema=1, items=[*previous['items'], item])


def bootstrap():
    r = helper('skill-platform-runtime')
    state = r.a.worker('overseas')
    raw = (Path('/proc') / str(state['pid']) / 'environ').read_bytes()
    env = dict(x.decode().split('=', 1) for x in raw.split(b'\0') if x)
    os.environ.update(env)
    os.environ['HX_BUSINESS_CONTEXT'] = 'overseas'
    sys.path.insert(0, state['cwd'])
    from app.overseas.management.installed_catalog import root_config
    assert root_config() == (ROOT, True), 'Wrong business or Skill root'
    return r, state


def prepare(work, source):
    from app.overseas.management.installed_catalog import release_manifest, verify_package
    from app.overseas.management.installed_tree import digest, tree
    from app.overseas.management.skill_install import copy_package, verify_bundle
    r, _ = bootstrap()
    assert not (work / 'skill-prepared.json').exists(), 'Already prepared'
    pointer = (ROOT / 'current.json').read_bytes()
    old = json.loads(pointer)['release']
    directory, previous = release_manifest(ROOT, old, True)
    package, entries = tree(source)
    expected = json.loads((work / 'source-manifest.json').read_text())
    assert entries == expected['entries'] and package.checksum == expected['checksum'], 'Source drift'
    combined = merged_manifest(previous, package, entries)
    combined['items'][-1].update(sourceChecksum=expected['originalChecksum'],
        sourceEntries=expected['originalEntries'], adaptedFiles=expected['adaptedFiles'])
    release = digest(combined)
    bundle = work / 'skill-bundles' / release
    bundle.mkdir(parents=True)
    for item in previous['items']:
        verified = verify_package(directory, item, True)
        copy_package(bundle / item['name'], verified, item['entries'], item['name'])
    copy_package(bundle / NAME, package, entries, NAME)
    (bundle / 'manifest.json').write_text(json.dumps(combined, ensure_ascii=False, sort_keys=True, indent=2))
    verify_bundle(bundle)
    assert (ROOT / 'current.json').read_bytes() == pointer, 'Catalog changed during preparation'
    r.private(work / 'skill-pointer-before.json', pointer.decode())
    r.private(work / 'skill-prepared.json', dict(old=old, release=release, sourceChecksum=package.checksum,
              previousItems=previous['items'], files=len(package.files), packages=len(combined['items'])))
    return dict(release=release, packages=len(combined['items']), addedFiles=len(package.files))


def install(work):
    from app.overseas.management.skill_install import install as publish
    r, _ = bootstrap()
    data = json.loads((work / 'skill-prepared.json').read_text())
    assert (ROOT / 'current.json').read_bytes() == (work / 'skill-pointer-before.json').read_bytes(), 'Catalog drift'
    before = r.sql(r.DB, "SELECT coalesce(json_agg(to_jsonb(t) ORDER BY id),'[]') FROM overseas_installed_skill_availability t")
    assert NAME not in {x['id'] for x in json.loads(before)}, 'Unexpected existing Skill settings'
    r.private(work / 'skill-settings-before.json', before)
    result = publish(work / 'skill-bundles' / data['release'])
    r.private(work / 'skill-installed.json', result)
    return verify(work)


def verify(work):
    from app.overseas.management.installed_catalog import release_manifest, verify_package
    r, state = bootstrap()
    data = json.loads((work / 'skill-prepared.json').read_text())
    assert json.loads((ROOT / 'current.json').read_text())['release'] == data['release'], 'Wrong release'
    directory, current = release_manifest(ROOT, data['release'], True)
    assert current['items'][:-1] == data['previousItems'], 'Existing package manifest changed'
    for item in current['items']:
        verify_package(directory, item, True)
    settings = r.sql(r.DB, "SELECT coalesce(json_agg(to_jsonb(t) ORDER BY id),'[]') FROM overseas_installed_skill_availability t")
    assert settings == (work / 'skill-settings-before.json').read_text(), 'Skill settings changed'
    api = json.loads(r.run('docker', 'exec', r.API, 'python', '-B', '-m',
                          'app.overseas.management.skill_install', 'verify', timeout=120))
    import pwd
    person = pwd.getpwnam('hengxin-overseas')
    def demote():
        os.setgroups([])
        os.setgid(person.pw_gid)
        os.setuid(person.pw_uid)
    native = json.loads(r.run(state['cwd'] + '/.venv/bin/python', '-B', '-m',
        'app.overseas.management.skill_install', 'verify', cwd=state['cwd'],
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}, preexec_fn=demote, timeout=120))
    for value in (api, native):
        assert value['release'] == data['release'] and value['packages'] == data['packages'], 'Runtime catalog mismatch'
    assert api['directoryIdentity'] == native['directoryIdentity'], 'Runtime directory mismatch'
    proof = dict(release=data['release'], packages=data['packages'], addedFiles=data['files'],
                 sourceChecksum=data['sourceChecksum'], settingsUnchanged=True, platforms=[], enabled=False,
                 apiVerified=True, nativeVerified=True)
    r.private(work / 'SKILL_VERIFIED.json', proof)
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'install', 'verify'))
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0, 'Root required'
    # Execute with the native interpreter; add its source/environment before importing app modules.
    bootstrap()
    os.umask(0o022)
    print(json.dumps(prepare(args.work, args.source) if args.action == 'prepare'
                     else globals()[args.action](args.work)))
