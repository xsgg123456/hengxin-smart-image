"""Install verified, explicitly scoped archives on the empty .245 target only."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import stat
import tarfile

from collect_runtime import CODE_ROOTS

PRIVATE = Path('/var/lib/hengxin-migration/lan-245')
BINARIES = ('/opt/hengxin-runtime/codex-0.162.1/codex', '/opt/hengxin-runtime/bwrap')
SKILLS = '/var/lib/hengxin-overseas/local-skills'
TLS = '/opt/1panel/www/sites/zhitu/ssl'
ARCHIVES = {'code': 'code-runtime.tar.gz', 'frontend': 'frontend-current.tar.gz',
            'skills': 'skills-current.tar.gz', 'private': 'private-tls-config.tar.gz'}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def guard_private():
    if socket.gethostname() != 'hengxin-ai-245':
        raise RuntimeError('target host mismatch')
    for p in (PRIVATE, *PRIVATE.parents):
        s = p.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
            raise RuntimeError('unsafe private path')
    if PRIVATE.stat().st_mode & 0o077:
        raise RuntimeError('private directory must not be shared')


def roots_for(kind):
    if kind == 'code':
        return [x.lstrip('/') for x in sorted(CODE_ROOTS)] + [x.lstrip('/') for x in BINARIES]
    if kind == 'frontend':
        return ['frontend/dist', 'release.json']
    if kind == 'skills':
        return [SKILLS.lstrip('/')]
    return [(TLS + '/fullchain.pem').lstrip('/'), (TLS + '/privkey.pem').lstrip('/'),
            'home/codex/auth/config.toml']


def safe_members(archive, roots):
    result = []
    seen = set()
    for m in archive.getmembers():
        name = m.name.rstrip('/')
        path = PurePosixPath(name)
        if (path.is_absolute() or '..' in path.parts or name != str(path)
                or name in seen or not (m.isfile() or m.isdir())):
            raise RuntimeError('unsafe or duplicate archive member')
        if not any(name == root or name.startswith(root + '/') for root in roots):
            raise RuntimeError('archive member outside approved scope')
        seen.add(name)
        result.append(m)
    if not result:
        raise RuntimeError('empty archive')
    return result


def destinations(kind):
    if kind == 'frontend':
        return [('frontend/dist', '/opt/hengxin-smart-image/frontend/dist')]
    return [(p, '/' + p) for p in roots_for(kind)]


def validate_dest(path):
    if path.exists() or path.is_symlink():
        raise RuntimeError('destination already exists; refusing overwrite: ' + str(path))
    for p in path.parents:
        if p.exists() or p.is_symlink():
            s = p.lstat()
            if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
                raise RuntimeError('unsafe destination ancestor: ' + str(p))


def verify(stage, kind, runtime):
    verified = 0
    if kind == 'code':
        expected_paths = set()
        for path, info in runtime['native_hashes'].items():
            p = Path(path)
            if p.name.startswith('.env') or p.suffix == '.pyc':
                continue
            target = stage / path.lstrip('/')
            expected_paths.add(path.lstrip('/'))
            if (not target.is_file() or sha(target) != info['sha256']
                    or target.stat().st_size != info['size']):
                raise RuntimeError('native content mismatch: ' + path)
            verified += 1
        binary_hashes = {}
        for line in (PRIVATE / 'runtime-binaries.sha256').read_text().splitlines():
            digest, path = line.split('  ', 1)
            binary_hashes[path] = digest
        if set(binary_hashes) != set(BINARIES):
            raise RuntimeError('unexpected runtime binary manifest')
        for binary in BINARIES:
            p = stage / binary.lstrip('/')
            expected_paths.add(binary.lstrip('/'))
            if (not p.is_file() or not p.stat().st_mode & 0o100
                    or sha(p) != binary_hashes[binary]):
                raise RuntimeError('runtime binary missing, changed or not executable')
        actual_paths = {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
        if actual_paths != expected_paths:
            raise RuntimeError('code archive file inventory mismatch')
    elif kind == 'frontend':
        expected = {p: v for p, v in runtime['frontend_release']['files'].items()
                    if p.startswith('frontend/dist/')}
        actual = {p.relative_to(stage).as_posix() for p in (stage / 'frontend/dist').rglob('*')
                  if p.is_file()}
        if set(expected) != actual:
            raise RuntimeError('frontend manifest inventory mismatch')
        for path, digest in expected.items():
            if sha(stage / path) != digest:
                raise RuntimeError('frontend checksum mismatch')
        verified = len(expected)
    elif kind == 'skills':
        before = (PRIVATE / 'skills-before.sha256').read_bytes()
        if before != (PRIVATE / 'skills-after.sha256').read_bytes():
            raise RuntimeError('source skills changed during copying')
        expected = {}
        for line in before.decode().splitlines():
            digest, relative = line.split('  ', 1)
            path = PurePosixPath(relative)
            if path.is_absolute() or '..' in path.parts or len(digest) != 64:
                raise RuntimeError('invalid source skill hash list')
            expected[str(path)] = digest
        root = stage / SKILLS.lstrip('/')
        actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
        if actual != set(expected):
            raise RuntimeError('skill file inventory mismatch')
        for relative, digest in expected.items():
            if sha(root / relative) != digest:
                raise RuntimeError('skill content mismatch')
        verified = len(expected)
    else:
        for relative in roots_for(kind):
            if not (stage / relative).is_file():
                raise RuntimeError('private config missing')
            (stage / relative).chmod(0o600)
        verified = len(roots_for(kind))
    return verified


def install(kind):
    guard_private()
    runtime = json.loads((PRIVATE / 'source-runtime.json').read_text())
    if runtime['host'] != 'racknerd-058889d':
        raise RuntimeError('unexpected source baseline')
    pairs = destinations(kind)
    for _, dest in pairs:
        validate_dest(Path(dest))
    stage = PRIVATE / ('stage-' + kind)
    stage.mkdir(mode=0o700)
    archive_path = PRIVATE / ARCHIVES[kind]
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = safe_members(archive, roots_for(kind))
        archive.extractall(stage, members=members, filter='data')
    verified = verify(stage, kind, runtime)
    installed = []
    for source, dest in pairs:
        src, dst = stage / source, Path(dest)
        validate_dest(dst)
        dst.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            # Exclusive creation prevents silently replacing an unexpected file.
            descriptor = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as output, src.open('rb') as content:
                shutil.copyfileobj(content, output)
            dst.chmod(src.stat().st_mode & 0o777)
        installed.append(str(dst))
    receipt = {'kind': kind, 'archive_sha256': sha(archive_path),
               'verified_files': verified, 'installed': installed}
    with (PRIVATE / ('installed-' + kind + '.json')).open('x') as output:
        json.dump(receipt, output)
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=tuple(ARCHIVES))
    install(parser.parse_args().kind)
