"""Whitelist production artifacts; never include runtime data or credentials."""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
app = repo / 'hengxin-smart-image'
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
status = json.loads(subprocess.check_output([sys.executable, '.codex/hooks/harness.py', 'review-status'], cwd=repo))
assert status['approved'], 'Current code must match independently approved snapshot'
release = 'annotation-20260924-' + commit[:7]
work = repo / 'output' / release
stage = work / 'src'
stage.mkdir(parents=True, exist_ok=False)
tracked = subprocess.check_output(['git', 'ls-files', '-z', 'hengxin-smart-image'], cwd=repo).decode('utf-8').split('\0')
names = []
exact = {'backend/pyproject.toml', 'backend/uv.lock', 'backend/alembic.ini', 'frontend/package.json',
         'frontend/pnpm-lock.yaml', 'infra/Dockerfile.backend', 'infra/compose.yaml',
         'infra/compose.vps.yaml', 'infra/compose.api-image.yaml', 'infra/nginx.vps.conf'}
for name in tracked:
    if not name:
        continue
    relative = Path(name).relative_to('hengxin-smart-image').as_posix()
    if relative.startswith(('backend/app/', 'backend/migrations/')) or relative in exact:
        names.append(relative)
for file in (app / 'frontend/dist').rglob('*'):
    if file.is_file() and 'demo-images' not in file.parts:
        names.append(file.relative_to(app).as_posix())
names.extend('scripts/release/' + name for name in (
    'image-inputs-deploy.sh', 'image-inputs-worker.py', 'image-inputs-frontend.py'))
for name in names:
    source = (repo if name.startswith('scripts/') else app) / name
    target = stage / name
    assert not source.is_symlink(), name
    assert source.suffix.lower() not in {'.db', '.sqlite', '.sqlite3', '.pem', '.key', '.map', '.pyc'}, name
    assert source.name not in {'.env', 'auth.json', 'credentials.json'}, name
    if source.suffix.lower() in {'.py', '.sh', '.js', '.json', '.html', '.css', '.yaml', '.toml', '.ini'}:
        content = source.read_text(encoding='utf-8')
        # Public Codex runtime convention, not a developer's home directory.
        if name == 'backend/app/execution/final_delivery.py':
            content = content.replace("PurePosixPath('/home/runner/.codex/generated_images')", 'PUBLIC_RUNTIME_PATH')
        if name == 'backend/app/execution/workspace.py':
            content = content.replace("'--setenv', 'CODEX_HOME', '/home/runner/.codex'", 'PUBLIC_RUNTIME_ENV')
        assert not re.search(r'sk-(?:proj|ant)-[A-Za-z0-9_-]{16,}|-----BEGIN .*PRIVATE KEY|[A-Z]:[/\\]Users[/\\]|/Users/|/home/[^/\s]+/\.codex', content), name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if source.suffix.lower() in {'.py', '.sh', '.yaml', '.toml', '.ini'}:
        target.write_bytes(target.read_bytes().replace(b'\r\n', b'\n'))
files = {name: hashlib.sha256((stage / name).read_bytes()).hexdigest() for name in sorted(names)}
manifest = {'release': release, 'commit': commit, 'candidateId': status['currentId'],
            'frontendVersion': json.loads((app / 'frontend/package.json').read_text())['version'],
            'migration': '0017', 'files': files}
(stage / 'release.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
with tarfile.open(work / 'release.tar.gz', 'w:gz') as archive:
    for file in sorted(stage.rglob('*')):
        if not file.is_file():
            continue
        info = archive.gettarinfo(str(file), arcname=file.relative_to(stage).as_posix())
        info.uid = info.gid = 0
        info.uname = info.gname = 'root'
        info.mode = 0o644
        with file.open('rb') as stream:
            archive.addfile(info, stream)
evidence = {'release': release, 'fileCount': len(files), 'bytes': (work / 'release.tar.gz').stat().st_size,
            'sha256': hashlib.sha256((work / 'release.tar.gz').read_bytes()).hexdigest()}
(work / 'package-audit.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
print(json.dumps(evidence))
