"""0.2.61 to 0.2.62 frontend-only switch; retain assets and verify the live install."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('archive_runtime', Path(__file__).with_name('archive-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
ENTRIES = r.ENTRIES
BASE_VERSION = r.BASE_VERSION


def atomic_copy(source, destination):
    r.require(not any(p.is_symlink() for p in (destination, *destination.parents)), 'Linked static destination')
    temporary = destination.with_name(destination.name + '.archive-new')
    owned = False
    try:
        with temporary.open('xb') as stream:
            owned = True
            stream.write(source.read_bytes())
        temporary.chmod(0o644)
        os.replace(temporary, destination)
    finally:
        if owned:
            temporary.unlink(missing_ok=True)


def switch(source, app, backup):
    manifest = r.verify_package(source)
    for path in (app, backup, *(app/name for name in ENTRIES)):
        r.safe(path)
    r.require(json.loads((app / 'frontend/package.json').read_text())['version'] == BASE_VERSION, 'Frontend baseline changed')
    source_dist, target_dist = source / 'frontend/dist', app / 'frontend/dist'
    for path in source_dist.rglob('*'):
        if path.is_file() and path.name not in ('index.html', 'index.html.gz'):
            target = target_dist / path.relative_to(source_dist)
            r.safe(target)
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
        if name == 'frontend/package.json' or name.startswith('frontend/dist/'):
            r.require(r.digest(app / name) == expected, 'Installed frontend checksum mismatch')
    r.private(backup / 'INSTALLED.json', {name:r.digest(app / name) if (app / name).exists() else None for name in ENTRIES})
    return 'FRONTEND_' + r.VERSION + '_INSTALLED'


def rollback(app, backup):
    r.safe(backup)
    for name in ENTRIES:
        r.safe(app/name)
        r.safe(backup/name)
    evidence = json.loads((backup / 'COMPLETE.json').read_text())
    saved = evidence['saved']
    r.require(set(saved) <= set(ENTRIES) and set(evidence['planned']) == set(ENTRIES), 'Unexpected backup scope')
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


def deploy(source, app, backup):
    r.verify_package(source)
    before = r.baseline(app)
    r.require(not backup.exists(), 'Backup already exists; inspect previous attempt')
    try:
        switch(source, app, backup)
        r.private(backup/'BASELINE.json', before)
        result = r.installed(source, app)
        r.require(r.baseline(app) == before, 'Backend or configuration changed')
        r.private(backup/'VERIFIED.json', result)
        return result
    except BaseException:
        if (backup/'COMPLETE.json').is_file():
            rollback(app, backup)
        raise


def verify(source, app, backup):
    r.require(json.loads((backup/'COMPLETE.json').read_text())['manifest'] == r.digest(source/'release.json'),
              'Release identity changed')
    result = r.installed(source, app)
    r.require(r.baseline(app) == json.loads((backup/'BASELINE.json').read_text()), 'Protected baseline changed')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('deploy','rollback','verify'))
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--app', type=Path, default=r.APP)
    parser.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    r.verify_package(args.source)
    if args.action == 'deploy':
        result = deploy(args.source,args.app,args.backup)
    elif args.action == 'verify':
        result = verify(args.source,args.app,args.backup)
    else:
        r.require(json.loads((args.backup/'COMPLETE.json').read_text())['manifest'] == r.digest(args.source/'release.json'),
                  'Backup belongs to another release')
        result = rollback(args.app,args.backup)
    print(json.dumps(result))
