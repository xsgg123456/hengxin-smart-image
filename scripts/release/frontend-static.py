"""Frontend-only release: audited archive, retained assets, recoverable HTML switch."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(repo):
    spec = importlib.util.spec_from_file_location('text_package', Path(__file__).with_name('package-text.py'))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    git = lambda *args: helper.common.git(repo, *args)
    assert not git('status', '--porcelain').strip(), 'Commit changes before packaging'
    status = helper.common.reviewed_status(repo)
    commit = git('rev-parse', 'HEAD').decode().strip()
    release = 'frontend-brand-20261006-' + commit[:7]
    source = repo / 'hengxin-smart-image/frontend'
    files = {}
    for path in (source / 'dist').rglob('*'):
        assert not path.is_symlink(), str(path)
        if not path.is_file() or 'demo-images' in path.parts:
            continue
        name = 'frontend/dist/' + path.relative_to(source / 'dist').as_posix()
        helper.audit_asset(name, path.read_bytes())
        files[name] = path.read_bytes()
    for name in ('hengxin-smart-image/frontend/package.json', 'scripts/release/frontend-static.py'):
        raw = helper.common.normalized(git('show', f'{commit}:{name}'))
        assert raw == helper.common.normalized((repo / name).read_bytes())
        helper.common.privacy_check(name, raw)
        files[name.removeprefix('hengxin-smart-image/')] = raw
    assert 'frontend/dist/index.html' in files
    assert json.loads(files['frontend/package.json'])['version'] == '0.2.19'
    manifest = dict(release=release, commit=commit, candidateId=status['currentId'],
                    frontendVersion='0.2.19', files={n: hashlib.sha256(b).hexdigest() for n, b in files.items()})
    files['release.json'] = json.dumps(manifest, indent=2).encode()
    raw = helper.archive_bytes(files)
    target = repo / 'output/release' / release
    target.mkdir(parents=True, exist_ok=False)
    (target / 'release.tar.gz').write_bytes(raw)
    result = dict(release=release, files=len(files), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), privacy='PASS')
    (target / 'package-audit.json').write_text(json.dumps(result, indent=2))
    assert not git('status', '--porcelain').strip()
    assert helper.common.reviewed_status(repo)['currentId'] == status['currentId']
    return result


def verify(source, manifest):
    for name, expected in manifest['files'].items():
        path = source / name
        assert path.resolve().is_relative_to(source.resolve()) and not path.is_symlink(), name
        assert digest(path) == expected, name


def atomic_copy(source, target):
    temporary = target.with_name(target.name + '.frontend-new')
    shutil.copyfile(source, temporary)
    temporary.chmod(0o644)
    os.replace(temporary, target)


def deploy(source, app, backup):
    manifest = json.loads((source / 'release.json').read_text())
    verify(source, manifest)
    assert manifest['frontendVersion'] == '0.2.19'
    target = app / 'frontend/dist'
    assert json.loads((app / 'frontend/package.json').read_text())['version'] == '0.2.18'
    # Unhashed assets may be shared by old HTML; refuse changing them in place.
    for file in (source / 'frontend/dist').rglob('*'):
        if not file.is_file() or file.name in ('index.html', 'index.html.gz'):
            continue
        dest = target / file.relative_to(source / 'frontend/dist')
        assert not any(p.is_symlink() for p in (dest, *dest.parents))
        assert not dest.exists() or digest(dest) == digest(file), str(dest)
    backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    entries = ('frontend/dist/index.html', 'frontend/dist/index.html.gz',
               'frontend/package.json', 'FRONTEND_RELEASE.json')
    present = [name for name in entries if (app / name).exists()]
    for name in present:
        dest = backup / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(app / name, dest)
        assert digest(dest) == digest(app / name)
    (backup / 'COMPLETE').write_text(json.dumps(present))
    try:
        for file in (source / 'frontend/dist').rglob('*'):
            if not file.is_file() or file.name in ('index.html', 'index.html.gz'):
                continue
            dest = target / file.relative_to(source / 'frontend/dist')
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                atomic_copy(file, dest)
        for directory in target.rglob('*'):
            if directory.is_dir():
                directory.chmod(0o755)
        for name in ('index.html.gz', 'index.html'):
            file = source / 'frontend/dist' / name
            if file.exists():
                atomic_copy(file, target / name)
            else:
                (target / name).unlink(missing_ok=True)
        atomic_copy(source / 'frontend/package.json', app / 'frontend/package.json')
        temporary = app / 'FRONTEND_RELEASE.json.frontend-new'
        temporary.write_text(json.dumps(manifest, indent=2))
        os.replace(temporary, app / 'FRONTEND_RELEASE.json')
        verify(app, {'files': {n: h for n, h in manifest['files'].items() if n.startswith('frontend/')}})
    except BaseException:
        for name in entries:
            if name in present:
                atomic_copy(backup / name, app / name)
            else:
                (app / name).unlink(missing_ok=True)
        raise
    return dict(release=manifest['release'], installedFiles=len(manifest['files']) - 1, backup=str(backup))


if __name__ == '__main__':
    os.umask(0o077)
    if sys.argv[1] == 'package':
        result = package(Path(__file__).resolve().parents[2])
    else:
        assert sys.argv[1] == 'deploy' and len(sys.argv) == 5
        result = deploy(*map(Path, sys.argv[2:]))
    print(json.dumps(result))
