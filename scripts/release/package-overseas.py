"""Package reviewed, committed overseas runtime and production frontend assets."""
import hashlib
import gzip
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

RELEASE_HELPERS = {'release-retention.py', 'release-retention-state.py',
                   'release-retention-docker.py', 'release-build.py'} | {
    path.name for path in Path(__file__).parent.glob('release-retention*.py')}


spec = importlib.util.spec_from_file_location('management_package', Path(__file__).with_name('package-management.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

APP = 'hengxin-smart-image/'
VERSION = '0.2.33'
EXACT = m.EXACT | {
    'backend/app/overseas/management/skill_inventory_20261013.json',
    'backend/alembic.overseas.ini',
    'backend/migrations/overseas/script.py.mako',
    'infra/compose.overseas.yaml', 'infra/compose.identity.yaml',
    'infra/overseas/bootstrap-postgres.sh', 'infra/overseas/bootstrap-minio.sh',
    'infra/hengxin-overseas-worker.service', 'infra/hengxin-overseas-outbox.service',
    'infra/nginx.zhitu.qhhengxin.top.conf', 'infra/nginx.overseas-upload.inc',
}
SCRIPTS = {'management-runtime.py', 'image-inputs-worker.py', 'native-studio-deploy.py', 'native-studio-runtime.py'} | RELEASE_HELPERS
MAINTENANCE = {'audit-business-members.py', 'reconcile-business-members.py', 'member_audit.py', 'member_catalog.py',
               'member_codec.py', 'member_cli.py', 'member_reconcile.py', 'member_restore.py'}
MEMBER_RELEASE = {'deploy', 'runtime', 'drain', 'backup', 'verify'}
REQUIRED = EXACT | {'scripts/release/' + n for n in SCRIPTS} | {
    'scripts/release/overseas-deploy.py', 'scripts/release/overseas-runtime.py',
    'scripts/release/overseas-verify.py', 'scripts/release/overseas-services.py',
    'scripts/release/overseas-topology.py',
    'scripts/release/overseas-update-deploy.py', 'scripts/release/overseas-update-runtime.py',
    'scripts/release/overseas-skills-runtime.py',
    'scripts/release/overseas-hotfix-deploy.py',
    'scripts/release/overseas-upload-deploy.py', 'scripts/release/overseas-upload-proxy.py',
    'scripts/release/overseas-upload-resources.py',
    'frontend/dist/index.html',
    'backend/migrations/env.py', 'backend/migrations/overseas/env.py',
    'backend/migrations/versions/0027_identity_session_binding.py',
    'backend/migrations/overseas/versions/0009_management.py',
    'backend/migrations/overseas/versions/0010_requirements_review.py',
    'backend/migrations/overseas/versions/0011_single_member_role.py',
    'backend/migrations/overseas/versions/0012_studio.py',
    'backend/migrations/overseas/versions/0013_task_deletion_archives.py',
    'backend/migrations/versions/0028_member_applications.py',
    'backend/migrations/overseas/versions/0014_member_applications.py',
    'backend/migrations/overseas/versions/0015_studio_transcript.py',
    'scripts/release/member-release-deploy.py',
    'backend/app/overseas/tasks/cleanup.py',
    'backend/app/overseas/tasks/deletion.py',
    'backend/app/overseas/archives/snapshot.py',
    'backend/app/overseas/management/installed_catalog.py',
    'backend/app/overseas/management/skill_install.py',
    'backend/app/overseas/studio/router.py',
    'backend/app/main.py', 'backend/app/identity/main.py',
    'backend/app/overseas/main.py', 'backend/app/overseas/execution/worker.py',
    'backend/app/overseas/execution/outbox.py',
} | {'scripts/maintenance/' + name for name in MAINTENANCE} | {
    'scripts/release/member-release-' + name + '.py' for name in MEMBER_RELEASE}


def selected(path):
    if path in {'scripts/release/' + name for name in RELEASE_HELPERS}:
        return path
    parts = PurePosixPath(path).parts
    if '\\' in path or path.startswith('/') or any(p.startswith('.') for p in parts):
        return None
    if path.startswith(APP):
        name = path[len(APP):]
        if name in EXACT or (name.endswith('.py') and name.startswith(
                ('backend/app/', 'backend/migrations/', 'backend/tests/'))):
            return name
    prefix = 'scripts/release/'
    if path.startswith(prefix):
        name = path[len(prefix):]
        if '/' not in name and (name in SCRIPTS or re.fullmatch(r'(?:overseas|member-release)[\w-]*\.py', name)):
            return path
    if path.startswith('scripts/maintenance/') and path.removeprefix('scripts/maintenance/') in MAINTENANCE:
        return path
    return None


def require_clean_tracked(git):
    if git('status', '--porcelain', '--untracked-files=no').strip():
        raise ValueError('Commit all tracked changes before packaging')


def no_symlink(path):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Symlink in package: ' + str(path))


def collect_assets(dist):
    no_symlink(dist)
    files = {}
    for path in sorted(dist.rglob('*')):
        relative = path.relative_to(dist)
        if 'demo-images' in relative.parts:
            continue
        no_symlink(path)
        if not path.is_file():
            continue
        name = 'frontend/dist/' + relative.as_posix()
        raw = path.read_bytes()
        audit_asset(name, raw, dist.parent / 'node_modules/pdfjs-dist')
        files[name] = raw
    return files


def audit_asset(name, raw, pdfjs):
    """Only exact files shipped by pinned pdfjs-dist may bypass generic asset suffixes."""
    plain = name.removesuffix('.gz')
    resource = re.fullmatch(r'frontend/dist/pdfjs-6\.4\.299/(cmaps/[\w.-]+\.bcmap|standard_fonts/[\w.-]+\.(?:pfb|ttf)|wasm/[\w.-]+\.(?:wasm|js))', plain)
    worker = re.fullmatch(r'frontend/dist/assets/pdf\.worker\.min-[A-Za-z0-9_-]+\.js', plain)
    if not resource and not worker:
        return m.audit_asset(name, raw)
    no_symlink(pdfjs)
    if json.loads((pdfjs / 'package.json').read_text(encoding='utf-8'))['version'] != '6.4.299':
        raise ValueError('PDF.js resource version mismatch')
    reference = pdfjs / (resource.group(1) if resource else 'build/pdf.worker.min.mjs')
    no_symlink(reference)
    body = gzip.decompress(raw) if name.endswith('.gz') else raw
    if body != reference.read_bytes():
        raise ValueError('PDF.js resource bytes differ from pinned dependency: ' + name)


def validate(files):
    if missing := REQUIRED - files.keys():
        raise ValueError('Missing required package files: ' + ', '.join(sorted(missing)))
    if json.loads(files['frontend/package.json'])['version'] != VERSION:
        raise ValueError('Frontend version must be ' + VERSION)
    index = files['frontend/dist/index.html'].decode('utf-8')
    if 'overseas-preview' in index or any(
            name.endswith(('overseas-preview.html', 'demo.html')) for name in files):
        raise ValueError('Preview frontend is not a production build')
    refs = re.findall(r'(?:src|href)=["\']/?(assets/[^"\'?#]+)', index)
    if not any(ref.endswith('.js') for ref in refs):
        raise ValueError('Production index must reference a JavaScript asset')
    for ref in refs:
        if 'frontend/dist/' + ref not in files:
            raise ValueError('Missing frontend entry asset: ' + ref)


def verify_archive(raw, files):
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        members = archive.getmembers()
        if len(members) != len(files) or {m.name for m in members} != files.keys():
            raise ValueError('Archive member set differs from package')
        for member in members:
            if not member.isfile():
                raise ValueError('Archive contains a non-regular file')
            if hashlib.sha256(archive.extractfile(member).read()).digest() != hashlib.sha256(files[member.name]).digest():
                raise ValueError('Archive hash mismatch: ' + member.name)


def build(repo):
    git = lambda *args: m.common.git(repo, *args)
    require_clean_tracked(git)
    status = m.common.reviewed_status(repo)
    commit = git('rev-parse', 'HEAD').decode().strip()
    tracked = git('ls-files', '-z').decode().split('\0')
    for helper in ('package-overseas.py', 'package-management.py', 'package-delivery.py'):
        if 'scripts/release/' + helper not in tracked:
            raise ValueError('Packaging helpers must be committed before use')
    files, exceptions = {}, {}
    for path in tracked:
        name = selected(path)
        if not name:
            continue
        local = repo / path
        no_symlink(local)
        raw = m.common.normalized(git('show', f'{commit}:{path}'))
        if raw != m.common.normalized(local.read_bytes()):
            raise ValueError('Working tree differs from commit: ' + path)
        found = m.common.privacy_check(name, raw)
        if found:
            exceptions[name] = found
        files[name] = raw
    files.update(collect_assets(repo / APP / 'frontend/dist'))
    validate(files)
    release = 'overseas-20261014-' + commit[:7]
    manifest = dict(release=release, commit=commit, candidateId=status['currentId'],
                    migration='0028', overseasMigration='overseas_0015', frontendVersion=VERSION,
                    files={n: hashlib.sha256(v).hexdigest() for n, v in sorted(files.items())})
    files['release.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    require_clean_tracked(git)
    if (git('rev-parse', 'HEAD').decode().strip() != commit
            or m.common.reviewed_status(repo)['currentId'] != status['currentId']):
        raise ValueError('Source changed during packaging')
    raw = m.archive_bytes(files)
    verify_archive(raw, files)
    target = repo / 'output/release' / release
    target.mkdir(parents=True, exist_ok=False)
    archive_path = target / 'release.tar.gz'
    archive_path.write_bytes(raw)
    saved = archive_path.read_bytes()
    verify_archive(saved, files)
    audit = dict(release=release, files=len(files), bytes=len(saved),
                 sha256=hashlib.sha256(saved).hexdigest(), privacy='PASS', archiveVerified=True,
                 syntheticFixtureExceptions=exceptions)
    (target / 'package-audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    return audit


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
