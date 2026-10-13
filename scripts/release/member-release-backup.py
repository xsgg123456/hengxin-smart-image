"""Restricted full database/config backups, isolated restore, and migration invariants."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

spec = importlib.util.spec_from_file_location('member_runtime', Path(__file__).with_name('member-release-runtime.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
DBS = {
    'domestic': (m.r.PREFIX + 'postgres-1', 'hengxin', 'hengxin'),
    'overseas': (m.u.PG, 'postgres', 'hengxin_overseas'),
}
ADDED = {
    'domestic': {'domestic_membership_applications', 'domestic_membership_application_events', 'domestic_member_audits'},
    'overseas': {'overseas_membership_applications', 'overseas_membership_application_events'},
}


def query(database, statement):
    container, user, name = database
    return m.run('docker', 'exec', container, 'psql', '-v', 'ON_ERROR_STOP=1', '-U', user,
                 '-d', name, '-Atc', statement, capture=True)


def fingerprint(database):
    names = query(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    result = {}
    for name in names:
        assert re.fullmatch(r'[a-z][a-z0-9_]*', name), 'Unexpected table identifier'
        if name in ('alembic_version', 'overseas_alembic_version'):
            continue
        # The one permitted existing-row change is checked independently, not ignored silently.
        row = "(to_jsonb(t)-'directory_state')" if name in ('users', 'overseas_members') else 'to_jsonb(t)'
        result[name] = query(database, f"SELECT count(*)||':'||md5(coalesce(string_agg(md5({row}::text),'' "
                                     f"ORDER BY {row}::text),'')) FROM public.\"{name}\" t")
    return result


def compare(before, after, group):
    assert set(after) - set(before) == ADDED[group], 'Unexpected migration table set'
    assert all(after.get(name) == value for name, value in before.items()), 'Existing business/identity records changed'
    assert all(after[name].startswith('0:') for name in ADDED[group]), 'Migration created applications/audits'


def verify_after(backup):
    before = json.loads((backup / 'fingerprints.json').read_text())
    after = {}
    for group, db in DBS.items():
        after[group] = fingerprint(db)
        compare(before[group], after[group], group)
        table = 'users' if group == 'domestic' else 'overseas_members'
        assert query(db, f"SELECT count(*) FROM {table} WHERE directory_state != "
                     "CASE WHEN status='pending' THEN 'legacy_unconfirmed' ELSE 'enrolled' END") == '0'
    m.private(backup / 'fingerprints-after.json', after)


def secure_tree(root):
    for path in (root, *root.rglob('*')):
        assert not path.is_symlink(), 'Symlink in private backup'
        path.chmod(0o700 if path.is_dir() else 0o600)


def save_file(destination, source):
    source = Path(source)
    assert source.is_file(), 'Required backup file missing: ' + str(source)
    target = destination / 'host' / str(source).lstrip('/')
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copyfile(source, target)
    target.chmod(0o600)


def backup_config(work, destination, data):
    m.private(destination / 'topology.json', data)
    for group in m.GROUPS:
        for path in data[group]['files']:
            save_file(destination, path)
        shutil.copyfile(work / (group + '-compose.private.json'), destination / (group + '-compose.private.json'))
    for relative in ('frontend/package.json', 'frontend/dist/index.html', 'infra/nginx.vps.conf'):
        save_file(destination, m.APP / relative)
    if (m.APP / 'frontend/dist/index.html.gz').exists():
        save_file(destination, m.APP / 'frontend/dist/index.html.gz')
    for path in m.APP.glob('*RELEASE.json'):
        save_file(destination, path)
    m.private(destination / 'edge.conf', (work / 'edge-before.conf').read_text())
    for unit in m.UNITS:
        for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles'):
            value = m.run('systemctl', 'show', unit, '-p', key, '--value', capture=True)
            # EnvironmentFiles includes systemd's "(ignore_errors=no)" metadata.
            files = [part for part in value.split() if part.startswith('/')]
            assert files or key == 'DropInPaths', 'Native service backup path missing'
            for path in files:
                save_file(destination, path)
        m.private(destination / (unit + '.unit.txt'), m.run('systemctl', 'cat', unit, capture=True))
    m.private(destination / 'native-pointers.json', data['native'])


def dump(database, target):
    container, user, name = database
    with target.open('wb') as stream:
        subprocess.run(['docker', 'exec', container, 'pg_dump', '-U', user, '-d', name, '-Fc'],
                       stdout=stream, check=True)
    target.chmod(0o600)
    assert target.stat().st_size > 0
    with target.open('rb') as stream:
        subprocess.run(['docker', 'exec', '-i', container, 'pg_restore', '--list'],
                       stdin=stream, stdout=subprocess.DEVNULL, check=True)


def restore_check(database, dumpfile, expected, release, group):
    image = m.live(database[0])['Image']
    name = 'hx-member-restore-' + release.removeprefix('overseas-') + '-' + group
    created = False
    try:
        m.run('docker', 'run', '--rm', '-d', '--network', 'none', '--name', name,
              '--mount', 'type=volume,dst=/var/lib/postgresql/data',
              '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', image, capture=True)
        created = True
        deadline = time.monotonic() + 60
        while True:
            try:
                m.run('docker', 'exec', name, 'pg_isready', '-U', 'postgres', capture=True)
                break
            except subprocess.CalledProcessError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(2)
        with dumpfile.open('rb') as stream:
            subprocess.run(['docker', 'exec', '-i', name, 'pg_restore', '--exit-on-error',
                            '--no-owner', '--no-acl', '-U', 'postgres', '-d', 'postgres'],
                           stdin=stream, stdout=subprocess.DEVNULL, check=True)
        assert fingerprint((name, 'postgres', 'postgres')) == expected, 'Isolated restored records differ'
    finally:
        if created:
            m.run('docker', 'rm', '-f', '-v', name, capture=True)


def create(work, destination, data, release):
    assert (work / 'EXECUTORS_STOPPED').exists()
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(destination, 0o700)
    backup_config(work, destination, data)
    fingerprints = {group: fingerprint(db) for group, db in DBS.items()}
    m.private(destination / 'fingerprints.json', fingerprints)
    for group, database in DBS.items():
        target = destination / (group + '.dump')
        dump(database, target)
        restore_check(database, target, fingerprints[group], release, group)
        assert fingerprint(database) == fingerprints[group], 'Database changed while backing up'
    secure_tree(destination)
    m.private(destination / 'COMPLETE', 'Both dumps parsed and restored in isolated temporary databases')
