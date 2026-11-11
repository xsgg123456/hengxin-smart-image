"""Read-only provenance for pre-catalog packages and applied LAN transactions."""
import json
from pathlib import Path, PurePosixPath
import tarfile

import artifact_gc
import snapshot


def read(u, path):
    u.safe(path)
    return json.loads(path.read_bytes())


def transaction(u, work):
    """Bind a transaction to its actual candidate, never infer success from its name."""
    u.safe(work)
    if not (work/'applied.json').exists() or (work/'rolled-back.json').exists():
        return None
    if (work/'prepared.json').exists():
        prepared = read(u, work/'prepared.json')
        if read(u, work/'applied.json').get('manifest') != prepared['release_manifest']:
            raise RuntimeError('Applied transaction manifest mismatch')
    elif (work/'web-prepared.json').exists():
        prepared = read(u, work/'web-prepared.json')
    else:
        return None
    candidate = work/'compose.candidate.json'
    u.safe(candidate)
    if snapshot.sha(candidate.read_bytes()) != prepared['candidate']:
        raise RuntimeError('Applied transaction candidate drift')
    config = json.loads(candidate.read_bytes())
    # New transaction owns the switched frontend source; full releases share it.
    web = config['services']['domestic-web']['volumes']
    values = [m['source'] for m in web if m.get('target') == '/usr/share/nginx/html']
    if len(values) != 1:
        raise RuntimeError('Unrecognized historical frontend mount')
    source = snapshot.release_path(Path(values[0]).parent)
    return str(source)


def package(u, path, sources):
    """Match package commit AND file digests against a retained immutable source."""
    u.safe(path)
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)) or len(names) > 30000 or sum(m.size for m in members) > 2 * 1024**3:
            raise RuntimeError('Invalid package inventory')
        try:
            item = archive.getmember('release-manifest.json')
        except KeyError:
            return []
        if not item.isfile() or item.size > 8 * 1024**2:
            raise RuntimeError('Invalid package manifest')
        manifest = json.load(archive.extractfile(item))
        if set(names) != set(manifest['files']) | {'release-manifest.json'}:
            raise RuntimeError('Package inventory mismatch')
        for member in members:
            p = PurePosixPath(member.name)
            if (not member.isfile() or str(p) != member.name or p.is_absolute()
                    or '..' in p.parts or '\\' in member.name):
                raise RuntimeError('Unsafe package member')
            if member.name != 'release-manifest.json':
                if p.parts[0] not in ('backend', 'frontend') or snapshot.sha(archive.extractfile(member).read()) != manifest['files'][member.name]:
                    raise RuntimeError('Package member checksum mismatch')
    matched = []
    for source in sources:
        m = snapshot.manifest(u, Path(source))
        if (manifest.get('commit') == m['commit'] and manifest.get('files')
                and all(m['files'].get(n) == h for n, h in manifest['files'].items())):
            matched.append(source)
    return matched


def backup_matches(u, backup, prepared):
    """Legacy initial backup: all native envs, DB identities and dump hashes agree."""
    preserved = read(u, backup/'preserved-hashes.json')
    prior = {r['path']: r['sha256'] for r in prepared['configs']}
    keys = {'/etc/hengxin-lan/' + name + '.env' for name in u.NATIVE}
    if len(keys) != 7 or any(k not in prior or preserved.get(k) != prior[k] for k in keys):
        return False
    summary = read(u, backup/'summary.json')
    for side in ('domestic', 'overseas'):
        row, dump = summary[side], backup/(side + '.dump')
        u.safe(dump)
        if (not row['archive_valid'] or row['container_id'] != prepared['data_containers'][side+'-postgres']
                or row['bytes'] != dump.stat().st_size or row['sha256'] != artifact_gc.digest(dump)):
            return False
    return summary['accounts_bytes'] == (backup/'accounts.tar').stat().st_size


def discover(u, store, sources):
    """Return recognized artifacts plus explicit unowned preparation directories."""
    found, unowned = {}, []
    parent = store.root/'intranet-transactions'
    folders = list(parent.iterdir()) if parent.exists() else []
    folders += list(u.ROOT.glob('unify-*'))
    for work in folders:
        if not work.is_dir():
            continue
        owner = transaction(u, work)
        if owner is None:
            unowned.append(str(work))
            continue
        kind = 'transaction' if work.parent == parent else 'legacy'
        found[str(work)] = {'kind': kind, 'owners': [str(work)], 'source': owner}
        if kind == 'legacy':
            backup = u.ROOT/('unified-backup-' + work.name.removeprefix('unify-'))
            if backup.is_dir():
                prepared = read(u, work/'prepared.json')
                if not backup_matches(u, backup, prepared):
                    unowned.append(str(backup))
                else:
                    found[str(backup)] = {'kind': 'legacy', 'owners': [str(work)], 'source': owner}
    for path in sorted(u.ROOT.glob('*.tar.gz')):
        owners = package(u, path, sources)
        if owners:
            found[str(path)] = {'kind': 'package', 'owners': owners}
        else:
            unowned.append(str(path))
    for pattern in ('ip-access-*', 'frontend-menu-fix-*', 'source-release-*'):
        unowned.extend(str(p) for p in u.ROOT.glob(pattern))
    return found, sorted(set(unowned))
