"""0.2.53 -> 0.2.54 retained-hash static release; explicit HTML-only rollback."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil

spec = importlib.util.spec_from_file_location('account_runtime', Path(__file__).with_name('account-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
ENTRIES = ('frontend/dist/index.html', 'frontend/dist/index.html.gz', 'frontend/package.json', 'FRONTEND_RELEASE.json')


def atomic_copy(source, destination):
    r.require(not any(p.is_symlink() for p in (destination, *destination.parents)), 'Linked static destination')
    temporary = destination.with_name(destination.name + '.account-new')
    with temporary.open('xb') as stream:
        stream.write(source.read_bytes())
    temporary.chmod(0o644)
    os.replace(temporary, destination)


def deploy(source, app, backup):
    manifest = r.verify_package(source)
    r.require(json.loads((app / 'frontend/package.json').read_text())['version'] == '0.2.53', 'Frontend baseline changed')
    source_dist, target_dist = source / 'frontend/dist', app / 'frontend/dist'
    for path in source_dist.rglob('*'):
        if path.is_file() and path.name not in ('index.html', 'index.html.gz'):
            target = target_dist / path.relative_to(source_dist)
            r.require(not target.exists() or r.digest(target) == r.digest(path), 'Existing shared asset collision')
    backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    saved = {}
    for name in ENTRIES:
        path = app / name
        if path.exists():
            target = backup / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            saved[name] = r.digest(target)
            r.require(saved[name] == r.digest(path), 'Frontend backup checksum mismatch')
    planned = {name:r.digest(source / name) if (source / name).is_file() else None for name in ENTRIES}
    planned['FRONTEND_RELEASE.json'] = r.digest(source / 'release.json')
    r.private(backup / 'COMPLETE.json', {'saved':saved, 'planned':planned, 'manifest':r.digest(source / 'release.json')})
    for path in source_dist.rglob('*'):
        if not path.is_file() or path.name in ('index.html', 'index.html.gz'):
            continue
        target = target_dist / path.relative_to(source_dist)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            atomic_copy(path, target)
    for path in target_dist.rglob('*'):
        if path.is_dir():
            path.chmod(0o755)
    for name in ('index.html.gz', 'index.html'):
        path = source_dist / name
        if path.exists():
            atomic_copy(path, target_dist / name)
        else:
            (target_dist / name).unlink(missing_ok=True)
    atomic_copy(source / 'frontend/package.json', app / 'frontend/package.json')
    atomic_copy(source / 'release.json', app / 'FRONTEND_RELEASE.json')
    for name, expected in manifest['files'].items():
        if name.startswith('frontend/'):
            r.require(r.digest(app / name) == expected, 'Installed frontend checksum mismatch')
    r.private(backup / 'INSTALLED.json', {name:r.digest(app / name) if (app / name).exists() else None for name in ENTRIES})
    return 'FRONTEND_0.2.54_INSTALLED'


def rollback(app, backup):
    evidence = json.loads((backup / 'COMPLETE.json').read_text())
    saved = evidence['saved']
    installed_path = backup / 'INSTALLED.json'
    installed = json.loads(installed_path.read_text()) if installed_path.exists() else None
    for name in ENTRIES:
        actual = r.digest(app / name) if (app / name).exists() else None
        allowed = {installed[name]} if installed else {saved.get(name), evidence['planned'][name]}
        r.require(actual in allowed, 'Frontend changed since deployment')
    for name, expected in saved.items():
        r.require(r.digest(backup / name) == expected, 'Frontend backup drift')
    # Hash resources remain so existing tabs and old HTML keep working.
    for name in ENTRIES:
        if name in saved:
            atomic_copy(backup / name, app / name)
        else:
            (app / name).unlink(missing_ok=True)
    return 'FRONTEND_ROLLED_BACK_HASH_ASSETS_RETAINED'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('deploy','rollback'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--app', type=Path, default=r.APP)
    parser.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    print(deploy(args.source,args.app,args.backup) if args.action == 'deploy' else rollback(args.app,args.backup))
