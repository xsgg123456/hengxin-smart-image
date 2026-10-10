"""Reviewed committed API-only release; reuse the audited asset/source allowlist."""
import hashlib
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('management_package', Path(__file__).with_name('package-management.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SCRIPTS = {'management-runtime.py', 'usage-total-deploy.py', 'usage-total-runtime.py', 'usage-total-verify.py'}


def selected(path):
    if path.startswith('hengxin-smart-image/'):
        return m.selected(path)
    if path.startswith('scripts/release/') and Path(path).name in SCRIPTS:
        return path
    return None


def validate(files):
    assert m.EXACT <= files.keys()
    assert {'scripts/release/' + name for name in SCRIPTS} <= files.keys()
    assert 'frontend/dist/index.html' in files
    assert json.loads(files['frontend/package.json'])['version'] == '0.2.21'
    for name in ('0024_cli_retention.py', '0025_api_usage_facts.py', '0026_api_worker_heartbeat.py'):
        assert 'backend/migrations/versions/' + name in files
    for name in ('app/contracts/api_usage.py', 'app/modules/management/api_usage.py',
                 'app/modules/management/api_usage_summary.py', 'tests/test_usage_generated_totals.py'):
        assert 'backend/' + name in files


def build(repo):
    git = lambda *args: m.common.git(repo, *args)
    m.require_clean_tracked(git)
    status = m.common.reviewed_status(repo)
    commit = git('rev-parse', 'HEAD').decode().strip()
    files = {}
    for path in git('ls-files', '-z').decode().split('\0'):
        name = selected(path)
        if not name:
            continue
        local = repo / path
        assert not local.is_symlink() and not any(p.is_symlink() for p in local.parents)
        raw = m.common.normalized(git('show', f'{commit}:{path}'))
        assert raw == m.common.normalized(local.read_bytes()), path
        m.common.privacy_check(name, raw)
        files[name] = raw
    dist = repo / 'hengxin-smart-image/frontend/dist'
    for path in dist.rglob('*'):
        if not path.is_file() or 'demo-images' in path.parts:
            continue
        assert not path.is_symlink() and not any(p.is_symlink() for p in path.parents)
        name = 'frontend/dist/' + path.relative_to(dist).as_posix()
        raw = path.read_bytes()
        m.audit_asset(name, raw)
        files[name] = raw
    validate(files)
    release = 'usage-total-20261010-' + commit[:7]
    manifest = dict(release=release, commit=commit, candidateId=status['currentId'],
        migration='0026', frontendVersion='0.2.21', services=['api'],
        files={n: hashlib.sha256(v).hexdigest() for n, v in sorted(files.items())})
    files['release.json'] = json.dumps(manifest, indent=2).encode()
    assert m.common.reviewed_status(repo)['currentId'] == status['currentId']
    m.require_clean_tracked(git)
    assert git('rev-parse', 'HEAD').decode().strip() == commit
    raw = m.archive_bytes(files)
    target = repo / 'output/release' / release
    target.mkdir(parents=True, exist_ok=False)
    (target / 'release.tar.gz').write_bytes(raw)
    audit = dict(release=release, files=len(files), bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(), privacy='PASS', archiveVerified=True)
    (target / 'package-audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    return audit


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
