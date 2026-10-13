"""Offline operator-only complete Skill publication; never executes package scripts."""
import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from .installed_catalog import read_catalog, release_manifest, root_config, verify_package
from .installed_tree import NAME, digest, safe_directory, tree


def definitions(source, mapping):
    source = safe_directory(Path(source))
    rows = json.loads(Path(mapping).read_text(encoding='utf-8'))
    names, paths, packages = set(), set(), []
    for row in rows:
        name, relative = row['name'], row['source']
        if (not NAME.fullmatch(name) or name in names or relative in paths
                or Path(relative).is_absolute() or '..' in Path(relative).parts
                or not isinstance(row.get('displayName'), str) or not 1 <= len(row['displayName'].strip()) <= 100):
            raise ValueError('Invalid or duplicate installation mapping')
        path = source / relative
        safe_directory(path)
        if not path.resolve().is_relative_to(source.resolve()):
            raise ValueError('Source escaped requested directory')
        package, entries = tree(path)
        names.add(name)
        paths.add(relative)
        packages.append((row, package, entries))
    if not packages:
        raise ValueError('Installation mapping is empty')
    return packages


def copy_package(destination, package, entries, name):
    destination.mkdir(parents=True)
    changes = []
    for relative, info in entries.items():
        path = destination / relative
        if info.get('directory'):
            path.mkdir(parents=True, exist_ok=True)
            continue
        data = package.files[relative]
        if name != package.name and path.suffix.lower() in ('.md', '.yaml', '.yml', '.py', '.sh', '.json', '.txt'):
            document = data.decode('utf-8')
            adapted = re.sub(r'(?<![a-z0-9_-])' + re.escape(package.name) + r'(?![a-z0-9_-])', name, document)
            if adapted != document:
                data = adapted.encode('utf-8')
                changes.append(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o755 if path.suffix.lower() in ('.sh', '.py') else 0o644)
    return changes


def bundle(source, mapping, output):
    packages = definitions(source, mapping)
    output = Path(output)
    if not output.is_absolute():
        raise ValueError('Bundle output must be absolute')
    output.mkdir(parents=True, exist_ok=True)
    safe_directory(output)
    staging = Path(tempfile.mkdtemp(prefix='.skill-build-', dir=output))
    try:
        items = []
        for row, original, entries in packages:
            changes = copy_package(staging / row['name'], original, entries, row['name'])
            installed, actual = tree(staging / row['name'])
            items.append(dict(name=row['name'], displayName=row['displayName'],
                description=installed.description, checksum=installed.checksum, entries=actual,
                source=row['source'], sourceName=original.name, sourceChecksum=original.checksum,
                sourceEntries=entries, adaptedFiles=changes))
        # Validate original trees once more before recording success.
        for row, original, _ in packages:
            if tree(Path(source) / row['source'])[0].checksum != original.checksum:
                raise ValueError('Source changed during bundle creation')
        manifest = dict(schema=1, items=items)
        release = digest(manifest)
        (staging / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False,
            sort_keys=True, indent=2), encoding='utf-8')
        destination = output / release
        if destination.exists():
            verify_bundle(destination)
        else:
            staging.rename(destination)
        return summary(release, items, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def verify_bundle(path):
    path = safe_directory(Path(path))
    from .installed_tree import read_file
    manifest = json.loads(read_file(path / 'manifest.json'))
    if manifest.get('schema') != 1 or digest(manifest) != path.name:
        raise ValueError('Bundle manifest integrity mismatch')
    if {p.name for p in path.iterdir()} != {i['name'] for i in manifest['items']} | {'manifest.json'}:
        raise ValueError('Bundle packages are missing or unexpected')
    names = set()
    for item in manifest['items']:
        if not NAME.fullmatch(item['name']) or item['name'] in names:
            raise ValueError('Invalid bundle Skill identifier')
        names.add(item['name'])
        verify_package(path, item)
    if not names:
        raise ValueError('Bundle is empty')
    return manifest


def install(bundle_path):
    root, protected = root_config()
    if protected and (os.name != 'posix' or os.geteuid() != 0):
        raise ValueError('Production Skill installation requires root operator')
    safe_directory(root, protected=protected)
    source = Path(bundle_path)
    manifest = verify_bundle(source)
    release = digest(manifest)
    releases = root / 'releases'
    releases.mkdir(exist_ok=True, mode=0o755)
    safe_directory(releases, protected=protected)
    staging = Path(tempfile.mkdtemp(prefix='.install-', dir=releases))
    temporary = None
    try:
        for item in manifest['items']:
            package, entries = tree(source / item['name'])
            copy_package(staging / item['name'], package, entries, package.name)
        (staging / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False,
            sort_keys=True, indent=2), encoding='utf-8')
        staging.chmod(0o755)
        for entry in staging.rglob('*'):
            if entry.is_dir():
                entry.chmod(0o755)
            elif entry.suffix.lower() not in ('.sh', '.py'):
                entry.chmod(0o644)
        # Do not give an immutable release its final name until copied bytes match.
        for item in manifest['items']:
            verify_package(staging, item, protected)
        destination = releases / release
        if not destination.exists():
            try:
                staging.rename(destination)
            except OSError:
                if not destination.exists():
                    raise
        directory, installed = release_manifest(root, release, protected)
        for item in installed['items']:
            verify_package(directory, item, protected)
        descriptor, filename = tempfile.mkstemp(prefix='.current-', dir=root)
        temporary = Path(filename)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump({'release': release}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)
        os.replace(temporary, root / 'current.json')
        if os.name == 'posix':
            descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return summary(release, installed['items'], destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if temporary and temporary.exists():
            temporary.unlink()


def summary(release, items, path=None):
    entries = [info for item in items for info in item['entries'].values() if 'size' in info]
    return dict(release=release, packages=len(items), files=len(entries),
                bytes=sum(info['size'] for info in entries), path=str(path) if path else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('preflight', 'bundle', 'install', 'verify'))
    parser.add_argument('--source')
    parser.add_argument('--mapping', default=str(Path(__file__).with_name('skill_inventory_20261013.json')))
    parser.add_argument('--output')
    parser.add_argument('--bundle')
    args = parser.parse_args()
    if args.command in ('bundle', 'preflight') and not args.source:
        parser.error('--source is required')
    if args.command == 'bundle':
        if not args.output:
            parser.error('--output is required')
        result = bundle(args.source, args.mapping, args.output)
    elif args.command == 'preflight':
        rows = definitions(args.source, args.mapping)
        result = summary(None, [dict(entries=entries) for _, _, entries in rows])
    elif args.command == 'install':
        if not args.bundle:
            parser.error('--bundle is required')
        result = install(args.bundle)
    else:
        root, protected = root_config()
        release, items = read_catalog(root, protected)
        result = summary(release, items, root)
        info = root.stat()
        result['directoryIdentity'] = dict(device=info.st_dev, inode=info.st_ino)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
