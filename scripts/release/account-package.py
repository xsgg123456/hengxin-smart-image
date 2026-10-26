"""Package reviewed account changes against captured production API source, never a whole API tree."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess


def helper(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def patch_sources(sources):
    result = {name: base64.b64decode(raw) for name, raw in sources.items()}
    for name in ('app/main.py', 'app/overseas/main.py'):
        prefix = '/api/v1' if name == 'app/main.py' else '/api/overseas/v1'
        assert b'codex_account_router' not in result[name]
        result[name] += ("\nfrom app.account_management.router import router as codex_account_router\n"
                         f"app.include_router(codex_account_router, prefix='{prefix}')\n").encode()
    name = 'app/core/config.py'
    anchor = b"    codex_auth_broker_socket: str = ''\n"
    assert result[name].count(anchor) == 1 and b'codex_account_management_socket' not in result[name]
    result[name] = result[name].replace(anchor, anchor + b"    codex_account_management_socket: str = ''\n")
    return result


def build(repo, baseline_path):
    common, text = helper('package-delivery'), helper('package-text')
    git = lambda *args: common.git(repo, *args)
    def clean_source():
        changed = set(git('diff', 'HEAD', '--name-only').decode().splitlines())
        untracked = git('ls-files', '--others', '--exclude-standard').decode().splitlines()
        assert changed <= {'AGENTS.md'} and not untracked, 'Commit reviewed release sources first'
        return hashlib.sha256((repo / 'AGENTS.md').read_bytes()).hexdigest()
    instructions_hash = clean_source()
    approved = common.reviewed_status(repo)
    commit = git('rev-parse', 'HEAD').decode().strip()
    baseline = json.loads(baseline_path.read_text(encoding='utf-8-sig'))
    release = 'account-management-20261026-' + commit[:7]
    files, apis = {}, {}
    backend = repo / 'hengxin-smart-image/backend'
    def source(name):
        path = backend / name
        assert path.is_file() and not path.is_symlink(), name
        raw = common.normalized(git('show', commit + ':hengxin-smart-image/backend/' + name))
        assert raw == common.normalized(path.read_bytes())
        common.privacy_check(name, raw)
        return raw
    api_new = {'app/account_management/' + n for n in ('client.py', 'router.py', 'schemas.py')}
    for domain in ('domestic', 'overseas'):
        original = baseline[domain]
        patch = patch_sources(original['sources'])
        patch.update({name: source(name) for name in api_new})
        apis[domain] = dict(image=original['image'], files={})
        for name, raw in patch.items():
            common.privacy_check(name, raw)
            files['api/' + domain + '/' + name] = raw
            old = base64.b64decode(original['sources'][name]) if name in original['sources'] else None
            apis[domain]['files'][name] = dict(baseline=hashlib.sha256(old).hexdigest() if old else None,
                                              sha256=hashlib.sha256(raw).hexdigest())
    execution = ('credential_broker', 'credential_broker_client', 'credential_identity', 'credential_errors',
                 'managed_credentials', 'managed_credentials_files', 'workspace', 'process')
    host = {'app/execution/' + n + '.py' for n in execution}
    host |= {p.relative_to(backend).as_posix() for p in (backend / 'app/account_management').glob('*.py')
             if p.name not in ('client.py', 'router.py', 'schemas.py')}
    assert 'app/account_management/service.py' in host
    for name in host:
        files['daemon/' + name] = source(name)
    for name in ('test_account_management_state.py', 'test_account_management_linux.py',
                 'test_managed_credentials.py', 'test_credential_broker.py'):
        files['tests/' + name] = source('tests/' + name)
    for path in sorted(Path(__file__).parent.glob('account-*.py')):
        name = path.relative_to(repo).as_posix()
        raw = common.normalized(git('show', commit + ':' + name))
        assert raw == common.normalized(path.read_bytes())
        common.privacy_check(name, raw)
        files[name] = raw
    asset = helper('package-overseas')
    files.update(asset.collect_assets(repo / 'hengxin-smart-image/frontend/dist'))
    package_name = 'hengxin-smart-image/frontend/package.json'
    raw = common.normalized(git('show', commit + ':' + package_name))
    assert raw == common.normalized((repo / package_name).read_bytes())
    assert json.loads(raw)['version'] == '0.2.54'
    files['frontend/package.json'] = raw
    manifest = dict(release=release, commit=commit, candidateId=approved['currentId'], frontendVersion='0.2.54',
                    apiUid=10001, apis=apis, baselineEvidenceSha256=hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
                    files={n:hashlib.sha256(b).hexdigest() for n,b in sorted(files.items())})
    files['release.json'] = json.dumps(manifest, indent=2).encode()
    archive = text.archive_bytes(files)
    assert common.reviewed_status(repo)['currentId'] == approved['currentId']
    assert clean_source() == instructions_hash
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
