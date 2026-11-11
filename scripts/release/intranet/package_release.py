"""Build a LAN release from committed Git bytes, never the working tree."""
import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile

PREFIX = 'hengxin-smart-image/'
ROOTS = tuple(PREFIX + name for name in ('backend', 'frontend'))
LAN_ENV = {'VITE_ACCESS_MODE': 'frontend', 'VITE_API_URL': '/api/v1', 'VITE_BASE_URL': '/'}
RENDERER = 'backend/app/execution/office_render.py'
RUNTIME_INPUTS = tuple(PREFIX + 'infra/' + name for name in (
    'CODEX-RUNTIME.md', 'codex-runtime-packages.txt',
    'install_codex_runtime.py', 'verify_codex_runtime.py'))
OMIT = {'node_modules', 'tests', '__pycache__', '.pytest_cache', '.mypy_cache',
        '.ruff_cache', '.git', '.venv', 'venv', 'coverage', '.cache'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


@contextmanager
def workspace():
    path = Path(tempfile.mkdtemp(prefix='hx-release-')).resolve()
    try:
        yield path
    finally:
        # pnpm's version manager can exceed MAX_PATH even when the project is short.
        cleanup_path = ('\\\\?\\' + str(path)) if os.name == 'nt' else str(path)
        shutil.rmtree(cleanup_path)


def safe_path(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '\\' in name or ':' in name
            or any(p in ('', '.', '..') for p in name.split('/'))):
        raise RuntimeError('Unsafe archive path: ' + name)
    return path


def excluded(name):
    parts = safe_path(name).parts
    leaf = parts[-1].lower()
    return (any(p.lower() in OMIT or p.lower() == 'dist' or p.lower().startswith('dist-') for p in parts)
            or (leaf.startswith('.env') and leaf != '.env.example')
            or leaf.endswith('.env')
            or leaf.endswith(('.pyc', '.pyo', '.pem', '.key', '.p12', '.pfx'))
            or leaf in {'id_rsa', 'id_ed25519', 'id_ecdsa', '.npmrc', '.yarnrc', '.yarnrc.yml'})


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def resolve_commit(repo, revision):
    if revision != 'HEAD' and not re.fullmatch('[0-9a-fA-F]{40}', revision):
        raise RuntimeError('Use HEAD or a full 40-character Git commit')
    commit = git(repo, 'rev-parse', '--verify', revision + '^{commit}').decode().strip()
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise RuntimeError('Only SHA-1 Git commits are supported')
    return commit


def extract_sources(repo, commit, destination):
    """Check archive inventory and bytes against Git blobs (including export attributes)."""
    expected = {}
    tree = git(repo, 'ls-tree', '-rz', commit, '--', *ROOTS)
    for row in tree.split(b'\0'):
        if not row:
            continue
        meta, raw_name = row.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        name = raw_name.decode('utf-8')
        safe_path(name)
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise RuntimeError('Links/submodules are forbidden: ' + name)
        if not excluded(name):
            expected[name] = oid
    archive = destination.parent / 'source.tar'
    git(repo, 'archive', '--format=tar', '--output=' + str(archive), commit, *ROOTS)
    seen, hashes, modes = set(), {}, {}
    with tarfile.open(archive) as source:
        for member in source:
            name = member.name.rstrip('/') if member.isdir() else member.name
            safe_path(name)
            if member.isdir():
                continue
            if not member.isfile():
                raise RuntimeError('Non-regular archive member: ' + name)
            if excluded(name):
                continue
            if name not in expected or name in seen:
                raise RuntimeError('Unexpected archive member: ' + name)
            data = source.extractfile(member).read()
            blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            if blob != expected[name]:
                raise RuntimeError('Archive bytes differ from Git: ' + name)
            if re.search(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----', data):
                raise RuntimeError('Private key material in source: ' + name)
            rel = name.removeprefix(PREFIX)
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as handle:
                handle.write(data)
            hashes[rel], modes[rel] = sha(data), 0o755 if member.mode & 0o111 else 0o644
            target.chmod(modes[rel])
            seen.add(name)
    if seen != set(expected) or not any(n.startswith('backend/') for n in hashes):
        raise RuntimeError('Git archive omitted source files')
    return hashes, modes


def build_environment(scratch, commit):
    # Explicit allowlist prevents host VITE_*, NODE_OPTIONS and registry tokens leaking in.
    allowed = {'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'PROCESSOR_ARCHITECTURE'}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    home, temp = scratch / 'home', scratch / 'tmp'
    home.mkdir()
    temp.mkdir()
    for name in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME'):
        env[name] = str(home)
    for name in ('TMP', 'TEMP', 'TMPDIR'):
        env[name] = str(temp)
    for name in ('userconfig', 'globalconfig'):
        config = scratch / (name + '.npmrc')
        config.touch()
        env['npm_config_' + name] = str(config)
    env.update({'npm_config_cache': str(scratch / 'npm-cache'), 'CI': 'true',
                'COREPACK_ENABLE_PROJECT_SPEC': '1', 'VITE_VERSION': commit[:12], **LAN_ENV})
    return env


def build_frontend(source, scratch, commit):
    frontend = source / 'frontend'
    package = json.loads((frontend / 'package.json').read_text(encoding='utf-8'))
    manager = 'pnpm' if (frontend / 'pnpm-lock.yaml').is_file() else 'npm'
    lock = 'pnpm-lock.yaml' if manager == 'pnpm' else 'package-lock.json'
    if not (frontend / lock).is_file():
        raise RuntimeError('A committed frontend dependency lockfile is required')
    executable = shutil.which(manager + ('.cmd' if os.name == 'nt' else ''))
    node = shutil.which('node')
    if not executable or not node:
        raise RuntimeError('Install the Node and package-manager versions declared in package.json')
    env = build_environment(scratch, commit)
    def version(command):
        return subprocess.check_output(command, cwd=frontend, env=env).decode().strip()
    node_version, manager_version = version([node, '--version']).removeprefix('v'), version([executable, '--version'])
    required_node = package.get('engines', {}).get('node')
    declared = package.get('packageManager', '').split('@')
    if required_node and node_version != required_node:
        raise RuntimeError('Node version must match package.json: ' + required_node)
    if len(declared) == 2 and (declared[0] != manager or declared[1] != manager_version):
        raise RuntimeError('Package manager must match package.json: ' + package['packageManager'])
    store = scratch / 'pnpm-store'
    if manager == 'pnpm':
        # Query only the cache location; install/build never inherit user config or tokens.
        store_env = {k: v for k, v in os.environ.items() if k.upper() in {
            'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'HOME', 'USERPROFILE',
            'APPDATA', 'LOCALAPPDATA', 'PNPM_HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME'}}
        store = Path(subprocess.check_output([executable, 'store', 'path', '--silent'],
                                            env=store_env).decode().strip())
        if not store.is_absolute() or not re.fullmatch(r'v\d+', store.name):
            raise RuntimeError('Cannot determine pnpm store root')
        store = store.parent
    install = (['install', '--frozen-lockfile', '--store-dir', str(store)]
               if manager == 'pnpm' else ['ci'])
    commands = [install, ['run', 'typecheck'], ['exec', 'vite', 'build', '--mode', 'production']]
    for command in commands:
        subprocess.run([executable, *command], cwd=frontend, env=env, check=True)
    return {'node': node_version, 'package_manager': manager + '@' + manager_version,
            'commands': [[manager, *cmd] if cmd is not install else [manager, *install[:2]]
                         for cmd in commands], 'environment': {**LAN_ENV, 'VITE_VERSION': commit[:12]},
            'lockfile': lock, 'lockfile_sha256': sha((frontend / lock).read_bytes())}


def write_package(source, output, commit, hashes, modes, build, runtime_inputs):
    payload = {}
    for name, expected in hashes.items():
        if name.startswith('backend/'):
            data = (source / name).read_bytes()
            if sha(data) != expected:
                raise RuntimeError('Backend changed during frontend build: ' + name)
            payload[name] = data
    dist = source / 'frontend/dist'
    if dist.is_symlink() or not (dist / 'index.html').is_file():
        raise RuntimeError('Build produced no regular frontend index')
    for path in sorted(dist.rglob('*')):
        if path.is_symlink():
            raise RuntimeError('Symlink in frontend output')
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError('Non-regular frontend output')
        name = 'frontend/' + path.relative_to(dist).as_posix()
        if excluded(name):
            raise RuntimeError('Forbidden frontend output: ' + name)
        payload[name] = path.read_bytes()
    if RENDERER not in payload:
        raise RuntimeError('Missing office renderer')
    manifest = {'commit': commit, 'files': {n: sha(v) for n, v in sorted(payload.items())},
                'frontend_current_files': {n: sha(v) for n, v in sorted(payload.items())
                                           if n.startswith('frontend/')},
                'runtime_inputs': runtime_inputs,
                'provenance': {'source_commit': commit, 'source_files': hashes, 'build': build}}
    payload['release-manifest.json'] = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    # Exclusive creation prevents overwriting a previous release or leaving a partial final file.
    with tempfile.TemporaryDirectory(prefix='hx-package-', dir=output.parent) as stage:
        staged = Path(stage) / 'release.tar.gz'
        with tarfile.open(staged, 'w:gz') as archive:
            for name, data in sorted(payload.items()):
                member = tarfile.TarInfo(name)
                member.size = len(data)
                member.mode = 0o755 if name == RENDERER else modes.get(name, 0o644)
                archive.addfile(member, io.BytesIO(data))
        with output.open('xb') as target, staged.open('rb') as finished:
            shutil.copyfileobj(finished, target)
    return manifest


def package_release(repo, revision, output):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    commit = resolve_commit(repo, revision)
    if output.exists():
        raise RuntimeError('Output already exists: ' + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    with workspace() as scratch:
        source = scratch / 'source'
        hashes, modes = extract_sources(repo, commit, source)
        build = build_frontend(source, scratch, commit)
        lock = 'frontend/' + build['lockfile']
        if build['lockfile_sha256'] != hashes.get(lock):
            raise RuntimeError('Dependency lockfile changed during build')
        runtime_inputs = {name: sha(git(repo, 'show', commit + ':' + name)) for name in RUNTIME_INPUTS
                          if git(repo, 'ls-tree', commit, '--', name).strip()}
        return write_package(source, output, commit, hashes, modes, build, runtime_inputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--commit', required=True, help='HEAD or full 40-character commit')
    parser.add_argument('--output', required=True, type=Path, help='New .tar.gz output path')
    args = parser.parse_args()
    try:
        result = package_release(args.repo, args.commit, args.output)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps({'commit': result['commit'], 'output': str(args.output.resolve()),
                      'files': len(result['files'])}))


if __name__ == '__main__':
    main()
