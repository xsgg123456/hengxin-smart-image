"""Build a reviewed, committed backend-only release with a closed file allowlist."""
import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

APP = 'hengxin-smart-image/'
PREVIOUS_IMAGE = 'hengxin-smart-image-backend:materials-20260924-2cdb4ff'
EXACT = {'backend/pyproject.toml', 'backend/uv.lock', 'backend/alembic.ini',
         'infra/Dockerfile.backend', 'backend/tests/fixtures/cli_revision_briefs.json',
         'backend/tests/fixtures/unannotated_revision_briefs.json'}
SCRIPTS = {'delivery-deploy.sh', 'delivery-native.py', 'image-inputs-worker.py'}
TESTS = {'test_delivery_deploy.py', 'test_delivery_native.py', 'test_package_delivery.py'}
SENSITIVE = re.compile(
    r'sk-[A-Za-z0-9_-]{16,}|-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----|'
    r'[A-Za-z]:[/\\]+Users[/\\]+|/Users/|/home/(?!runner/)[^/\s]+/\.codex')
# Exact existing synthetic negative fixtures, never a blanket exemption for tests.
FIXTURES = {
    'backend/tests/test_public_messages.py': (
        "'-----BEGIN PRIVATE KEY-----'", r"'C:\\Users\\private\\result.png'"),
    'backend/tests/test_round_materials.py': (r'C:\\Users\\secret.png',),
}


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo)


def normalized(data):
    return data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def selected(name):
    if name.startswith(APP):
        relative = name[len(APP):]
        if relative in EXACT or (relative.endswith('.py') and relative.startswith(
                ('backend/app/', 'backend/migrations/', 'backend/tests/'))):
            return relative
    prefix = 'scripts/release/'
    if name.startswith(prefix) and name[len(prefix):] in SCRIPTS | TESTS:
        return name
    return None


def privacy_check(name, content):
    text = content.decode('utf-8')
    exceptions = []
    for fixture in FIXTURES.get(name, ()):
        if fixture in text:
            # A duplicated fixture is unexpected and requires explicit review.
            if text.count(fixture) != 1:
                raise ValueError(f'Duplicated privacy fixture: {name}')
            text = text.replace(fixture, 'SYNTHETIC_NEGATIVE_FIXTURE')
            exceptions.append('existing synthetic negative fixture')
    if SENSITIVE.search(text):
        raise ValueError(f'Privacy scan failed: {name}')
    return exceptions


def reviewed_status(repo):
    result = subprocess.check_output(
        [sys.executable, '.codex/hooks/harness.py', 'review-status'], cwd=repo)
    status = json.loads(result)
    if not status.get('approved') or not status.get('currentId'):
        raise ValueError('Current source must match an independently approved snapshot')
    return status


def collect(repo, commit):
    # Ignore unrelated untracked documentation, but never staged/unstaged changes.
    if git(repo, 'diff', '--name-only', 'HEAD', '--').strip():
        raise ValueError('Tracked working tree must be clean and committed')
    tracked = git(repo, 'ls-files', '-z').decode('utf-8').rstrip('\0').split('\0')
    if 'scripts/release/package-delivery.py' not in tracked:
        raise ValueError('Packaging script must be committed before use')
    files, exceptions = {}, {}
    for source_name in tracked:
        name = selected(source_name)
        if not name:
            continue
        path = repo / source_name
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != repo):
            raise ValueError(f'Symlink not permitted: {source_name}')
        committed = git(repo, 'show', f'{commit}:{source_name}')
        content = normalized(path.read_bytes())
        if content != normalized(committed):
            raise ValueError(f'Working tree differs from commit: {source_name}')
        found = privacy_check(name, content)
        if found:
            exceptions[name] = found
        files[name] = content
    required = EXACT | {'scripts/release/' + name for name in SCRIPTS}
    if missing := required - files.keys():
        raise ValueError('Missing required tracked sources: ' + ', '.join(sorted(missing)))
    if not any(name.startswith('backend/migrations/versions/0017') for name in files):
        raise ValueError('Migration 0017 is missing')
    return files, exceptions


def build(repo):
    commit = git(repo, 'rev-parse', 'HEAD').decode().strip()
    status = reviewed_status(repo)
    files, exceptions = collect(repo, commit)
    release = 'delivery-20260927-' + commit[:7]
    manifest = {'release': release, 'commit': commit, 'candidateId': status['currentId'],
                'migration': '0017', 'backendOnly': True,
                'expectedPreviousImage': PREVIOUS_IMAGE,
                'files': {name: hashlib.sha256(data).hexdigest()
                          for name, data in sorted(files.items())}}
    files['release.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    # Recheck after reading files; archive bytes are now immutable in memory.
    if (git(repo, 'rev-parse', 'HEAD').decode().strip() != commit
            or git(repo, 'diff', '--name-only', 'HEAD', '--').strip()
            or reviewed_status(repo)['currentId'] != status['currentId']):
        raise ValueError('Source changed during packaging')
    work = repo / 'output' / 'release' / release
    work.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        target = work / 'src' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    archive_path = work / 'release.tar.gz'
    with archive_path.open('wb') as stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as archive:
                for name, data in sorted(files.items()):
                    info = tarfile.TarInfo(name)
                    info.size, info.mode = len(data), 0o644
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = 'root'
                    archive.addfile(info, io.BytesIO(data))
    with tarfile.open(archive_path, 'r:gz') as archive:
        for member in archive.getmembers():
            data = archive.extractfile(member).read()
            if data != files[member.name]:
                raise ValueError('Archive verification failed')
    evidence = {'release': release, 'fileCount': len(manifest['files']),
                'bytes': archive_path.stat().st_size,
                'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                'privacy': 'PASS', 'syntheticFixtureExceptions': exceptions,
                'archiveVerified': True, 'backendOnly': True}
    (work / 'package-audit.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    return evidence


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2]), ensure_ascii=False))
