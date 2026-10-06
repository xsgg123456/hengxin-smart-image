"""Committed source + production assets, closed allowlist and byte-verified archive."""
import gzip
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path
import subprocess
import tarfile

spec = importlib.util.spec_from_file_location('delivery_package', Path(__file__).with_name('package-delivery.py'))
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
EXACT = {'backend/pyproject.toml', 'backend/uv.lock', 'backend/alembic.ini',
         'infra/nginx.vps.conf', 'infra/nginx.media.conf',
         'frontend/package.json', 'infra/Dockerfile.backend',
         'backend/tests/fixtures/cli_revision_briefs.json',
         'backend/tests/fixtures/unannotated_revision_briefs.json',
         'backend/app/modules/api_image_edits/image_edit_prompt.txt',
        'backend/app/modules/api_image_edits/text_edit_prompt.txt',
         'backend/app/modules/api_image_edits/text_repair_prompt.txt'}
ASSET_SENSITIVE = re.compile(common.SENSITIVE.pattern.replace('sk-', r'(?<![A-Za-z0-9_])sk-', 1))


def selected(path):
    prefix = 'hengxin-smart-image/'
    if path.startswith(prefix):
        name = path[len(prefix):]
        if name in EXACT or (name.endswith('.py') and name.startswith(
                ('backend/app/', 'backend/migrations/', 'backend/tests/'))):
            return name
    if path.startswith('scripts/release/') and path.endswith('.py'):
        if Path(path).name in ('api-edit-deploy.py', 'api-edit-runtime.py', 'api-edit-verify.py', 'image-inputs-worker.py'):
            return path
    return None


def archive_bytes(files):
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w', format=tarfile.USTAR_FORMAT) as tar:
            for name, data in sorted(files.items()):
                if name.startswith('/') or '..' in Path(name).parts:
                    raise ValueError('Unsafe archive member')
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                tar.addfile(info, io.BytesIO(data))
    raw = buffer.getvalue()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
        assert {m.name: tar.extractfile(m).read() for m in tar} == files
    return raw


def audit_asset(name, raw):
    path = Path(name)
    if any(part.startswith('.') for part in path.parts) or re.search(
            r'(^|[./_-])(env|credentials?|auth|sessions?|secrets?|tokens?|passwords?)([./_-]|$)', name, re.I):
        raise ValueError('Sensitive asset filename: ' + name)
    if path.suffix == '.gz':
        if Path(path.stem).suffix not in ('.js', '.css', '.html', '.svg'):
            raise ValueError('Unsupported compressed asset: ' + name)
        return audit_asset(name[:-3], gzip.decompress(raw))
    if path.suffix not in ('.js', '.css', '.html', '.svg', '.png', '.jpg', '.jpeg',
                           '.webp', '.ico', '.woff', '.woff2', '.ttf'):
        raise ValueError('Unsupported asset: ' + name)
    if path.suffix in ('.js', '.css', '.html', '.svg'):
        if ASSET_SENSITIVE.search(raw.decode('utf-8')):
            raise ValueError('Privacy scan failed: ' + name)
    elif re.search(common.SENSITIVE.pattern.encode('ascii'), raw):
        raise ValueError('Privacy scan failed: ' + name)


def build(repo):
    git = lambda *args: common.git(repo, *args)
    if git('status', '--porcelain', '--untracked-files=no').strip():
        raise ValueError('Commit tracked changes before packaging')
    status = common.reviewed_status(repo)
    commit = git('rev-parse', 'HEAD').decode().strip()
    release = 'api-edit-20261006-' + commit[:7]
    files = {}
    for path in git('ls-files', '-z').decode().split('\0'):
        name = selected(path)
        if not name:
            continue
        local = repo / path
        if local.is_symlink() or any(p.is_symlink() for p in local.parents if p != repo):
            raise ValueError('Symlink in package')
        raw = common.normalized(git('show', f'{commit}:{path}'))
        assert raw == common.normalized(local.read_bytes()), path
        common.privacy_check(name, raw)
        files[name] = raw
    dist = repo / 'hengxin-smart-image/frontend/dist'
    for path in dist.rglob('*'):
        if not path.is_file() or 'demo-images' in path.parts:
            continue
        assert not path.is_symlink() and not any(p.is_symlink() for p in path.parents if p != repo)
        name = 'frontend/dist/' + path.relative_to(dist).as_posix()
        raw = path.read_bytes()
        audit_asset(name, raw)
        files[name] = raw
    assert EXACT <= files.keys() and 'frontend/dist/index.html' in files
    validate(files)
    manifest = {'release': release, 'commit': commit, 'candidateId': status['currentId'],
        'migration': '0023', 'frontendVersion': '0.2.17',
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files['release.json'] = json.dumps(manifest, indent=2).encode()
    assert common.reviewed_status(repo)['currentId'] == status['currentId']
    assert not git('status', '--porcelain', '--untracked-files=no').strip()
    assert git('rev-parse', 'HEAD').decode().strip() == commit
    raw = archive_bytes(files)
    target = repo / 'output/release' / release
    target.mkdir(parents=True, exist_ok=False)
    (target / 'release.tar.gz').write_bytes(raw)
    audit = {'release': release, 'files': len(files), 'bytes': len(raw),
             'sha256': hashlib.sha256(raw).hexdigest(), 'privacy': 'PASS', 'archiveVerified': True}
    (target / 'package-audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    return audit


def validate(files):
    assert {'infra/nginx.vps.conf', 'infra/nginx.media.conf'} <= files.keys()
    assert {
        'backend/app/modules/api_image_edits/image_edit_prompt.txt',
        'backend/app/modules/api_image_edits/text_edit_prompt.txt',
        'backend/app/modules/api_image_edits/text_repair_prompt.txt',
    } <= files.keys()
    assert 'backend/migrations/versions/0023_api_cli_conversations.py' in files
    assert json.loads(files['frontend/package.json'])['version'] == '0.2.17'
    assert {'scripts/release/' + n for n in (
        'api-edit-deploy.py', 'api-edit-runtime.py', 'api-edit-verify.py', 'image-inputs-worker.py')} <= files.keys()


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
