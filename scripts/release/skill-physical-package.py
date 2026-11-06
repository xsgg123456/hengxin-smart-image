"""Build manifest-pinned candidates or reviewed committed physical-Skill releases."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


spec = importlib.util.spec_from_file_location('physical_runtime', Path(__file__).with_name('skill-physical-runtime.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
r = p.r
FILES = p.load('skill-physical-baseline').FILES
TESTS = {
    'api': ['test_skill_object_storage.py', 'test_skill_offline_objects.py',
        'test_skill_physical_history.py', 'test_skill_physical_cleanup.py', 'test_skill_physical_maintenance.py',
        'test_skill_preparation_accounting.py', 'test_skill_publisher_recovery.py',
        'test_skill_history_durability.py',
        'test_overseas_installed_skills.py', 'test_overseas_installed_titles.py',
        'test_overseas_skill_transfers.py', 'test_overseas_skill_transfers_failures.py',
        'test_studio_skill_cache.py', 'test_studio_skill_cache_safety.py'],
    'native': ['test_studio_skill_cache.py', 'test_studio_skill_cache_safety.py'],
    'root': ['test_studio_skill_cache_linux.py', 'test_skill_object_storage.py'],
}


def old_digest(encoded):
    return hashlib.sha256(base64.b64decode(encoded, validate=True)).hexdigest() if encoded is not None else None


def baseline_manifest(baseline):
    r.require(baseline.get('kind') == 'skill-physical-baseline' and
              baseline['frontendVersion'] == '0.2.64' and baseline['revision'] == 'overseas_0026',
              'Unexpected physical baseline')
    for key in ('sources', 'publisherSources'):
        r.require(set(baseline[key]) == FILES, 'Baseline patch scope mismatch')
    for key in ('image', 'publisherImage'):
        r.require(re.fullmatch('sha256:[a-f0-9]{64}', baseline[key]), 'Invalid baseline image')
    r.require(set(baseline['nativeSources']) == set(r.UNITS) == set(baseline['units']),
              'Native identity baseline missing')
    native, roots = {'units': {}}, {}
    for unit in r.UNITS:
        saved = baseline['units'][unit]
        r.require(saved['uid'] == 999 and saved['pid'] > 0 and saved['cwd'] == saved['WorkingDirectory'] and
                  saved['cwd'].startswith('/opt/hengxin-overseas-releases/') and
                  saved['cwd'].endswith('/backend'), 'Unexpected native runtime identity')
        r.require(set(baseline['nativeSources'][unit]) == FILES, 'Native source scope mismatch')
        values = {name: old_digest(raw) for name, raw in baseline['nativeSources'][unit].items()}
        r.require(saved['cwd'] not in roots or roots[saved['cwd']] == values, 'Shared native baseline conflict')
        roots[saved['cwd']] = values
        native['units'][unit] = {'files': values}
    r.FILES = r.base.FILES = r.b.FILES = set(FILES)
    r.NATIVE_FILES = set(FILES)
    return r.native_baselines(native)


def build(repo, baseline_path, candidate=False):
    common = r.helper('package-delivery')
    git = lambda *args: common.git(repo, *args)
    identity = lambda: json.loads(subprocess.check_output(
        [sys.executable, '.codex/hooks/harness.py', 'review-status'], cwd=repo))

    def clean():
        r.require(not git('diff', 'HEAD', '--name-only').strip(), 'Commit release sources first')
        r.require(not git('ls-files', '--others', '--exclude-standard').strip(), 'Untracked release sources')

    if not candidate:
        clean()
    approved = identity() if candidate else common.reviewed_status(repo)
    r.require(re.fullmatch('[a-f0-9]{64}', approved.get('currentId', '')), 'Prepare harness candidate first')
    commit = git('rev-parse', 'HEAD').decode().strip()
    baseline_bytes = baseline_path.read_bytes()
    baseline = json.loads(baseline_bytes.decode('utf-8-sig'))
    native = baseline_manifest(baseline)
    files, captured, patches, exceptions = {}, {}, {}, {}

    def source(name):
        path = repo/name
        r.require(not any(part.is_symlink() for part in (path, *path.parents)), 'Linked source: '+name)
        raw = common.normalized(path.read_bytes())
        if not candidate:
            r.require(raw == common.normalized(git('show', commit+':'+name)), 'Source drift: '+name)
        audit_name = name.removeprefix('hengxin-smart-image/')
        found = common.privacy_check(audit_name, raw)
        if found:
            exceptions[audit_name] = found
        captured[name] = raw
        return raw

    for name in sorted(FILES):
        files['api/'+name] = source('hengxin-smart-image/backend/'+name)
    for role, key in (('api', 'sources'), ('publisher', 'publisherSources')):
        patches[role] = {name: dict(baseline=old_digest(baseline[key][name]),
            sha256=hashlib.sha256(files['api/'+name]).hexdigest()) for name in sorted(FILES)}
    package = r.helper('sku-package')
    package.r = r
    r.TESTS = tuple(sorted(set().union(*[set(names) for names in TESTS.values()])))
    files.update(package.collect_tests(repo/'hengxin-smart-image/backend/tests',
        lambda name: source('hengxin-smart-image/backend/tests/'+name)))
    for name in p.HELPERS:
        path = 'scripts/release/'+name+'.py'
        files[path] = source(path)
    build_proof, build_log = None, b''
    r.verify_frontend = p.load('polling-runtime').verify_frontend
    if candidate:
        assets = r.helper('package-overseas').collect_assets(repo/'hengxin-smart-image/frontend/dist')
        r.verify_frontend(assets['frontend/dist/index.html'].decode(), assets)
    else:
        assets, build_proof, build_log = r.helper('studio-batch-build').build(repo, commit, r)
    files.update(assets)
    files['frontend/package.json'] = source('hengxin-smart-image/frontend/package.json')
    version = json.loads(files['frontend/package.json'])['version']
    r.require(version == '0.2.65', 'Frontend version mismatch')
    release = 'skill-physical-20261106-'+('candidate-'+approved['currentId'][:12] if candidate else commit[:7])
    manifest = dict(kind='skill-physical', release=release, version=version, revision=baseline['revision'],
        commit=commit, candidateId=approved['currentId'], mode='candidate' if candidate else 'release',
        baseline={'frontendVersion': baseline['frontendVersion']},
        api={'image': baseline['image'], 'files': patches['api']},
        publisher={'image': baseline['publisherImage'], 'files': patches['publisher']}, native=native,
        tests=TESTS, baselineEvidenceSha256=hashlib.sha256(baseline_bytes).hexdigest(),
        files={name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())})
    if build_proof is not None:
        manifest['frontendBuild'] = build_proof
    files['release.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    # Run the exact deployed verifier against materialized package bytes before publishing an archive.
    with tempfile.TemporaryDirectory(prefix='skill-physical-verify-') as folder:
        root = Path(folder)
        for name, raw in files.items():
            path = root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        r.verify_package(root)
    archive = r.helper('package-text').archive_bytes(files)
    if not candidate:
        clean()
        r.require(common.reviewed_status(repo)['currentId'] == approved['currentId'], 'Review changed')
    r.require(git('rev-parse', 'HEAD').decode().strip() == commit and identity()['currentId'] == approved['currentId'],
              'Source identity changed')
    r.require(all(common.normalized((repo/name).read_bytes()) == raw for name, raw in captured.items()), 'Source drift')
    r.require(baseline_path.read_bytes() == baseline_bytes, 'Baseline changed during packaging')
    if candidate:
        r.require(r.helper('package-overseas').collect_assets(repo/'hengxin-smart-image/frontend/dist') == assets,
                  'Frontend build changed during packaging')
    target = repo/'output/release'/release
    target.mkdir(parents=True, exist_ok=False)
    (target/'release.tar.gz').write_bytes(archive)
    if build_proof is not None:
        (target/'frontend-build.log').write_bytes(build_log)
    audit = dict(release=release, sha256=hashlib.sha256(archive).hexdigest(), bytes=len(archive),
        fileCount=len(files), mode=manifest['mode'], candidateId=approved['currentId'], privacy='PASS',
        syntheticFixtureExceptions=exceptions, archiveVerified=True, frontendBuild=build_proof)
    (target/'package-audit.json').write_text(json.dumps(audit, indent=2)+'\n', encoding='utf-8')
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', action='store_true')
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[2], args.baseline, args.candidate)))
