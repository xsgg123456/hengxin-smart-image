"""Logical backup drill, exclusively inside the caller-owned disposable PG container."""
import hashlib
import re
import subprocess


def verify(container, environment):
    if not re.fullmatch(r'hx-p25-[0-9a-f]{12}-postgres', container):
        raise ValueError('Restore drill requires this invocation\'s Phase25 PostgreSQL container')

    def execute(*args, data=None):
        result = subprocess.run(['docker', 'exec', '-i', container, *args], input=data,
                                capture_output=True, env=environment)
        if result.returncode:
            raise RuntimeError('Disposable database restore failed: ' + result.stderr.decode(errors='replace'))
        return result.stdout

    def sql(database, statement):
        return execute('psql', '-X', '-U', 'postgres', '-d', database, '-v', 'ON_ERROR_STOP=1',
                       '-A', '-t', '-c', statement).decode().strip()

    def snapshot(database):
        names = sql(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
        assert names and 'overseas_jobs' in names and 'overseas_archives' in names
        facts = {}
        for name in names:
            # Identifiers come from our own migration-created catalog, never user SQL.
            assert re.fullmatch(r'[a-z_][a-z0-9_]*', name)
            rows = sql(database, f'SELECT row_to_json(t)::text FROM public."{name}" t ORDER BY row_to_json(t)::text COLLATE "C"')
            count = int(sql(database, f'SELECT count(*) FROM public."{name}"'))
            facts[name] = (count, hashlib.sha256(rows.encode()).hexdigest())
        sequences = sql(database, "SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")
        for name in sequences.splitlines():
            assert re.fullmatch(r'[a-z_][a-z0-9_]*', name)
            facts['sequence:' + name] = sql(database, f'SELECT last_value,is_called FROM public."{name}"')
        return facts

    # The caller only invokes this after all three API processes exit: stable write boundary.
    before = snapshot('overseas')
    domestic = sql('domestic', "SELECT version_num FROM alembic_version")
    assert domestic == '0027'
    assert sql('overseas', 'SELECT version_num FROM overseas_alembic_version') == 'overseas_0009'
    for name in ('overseas_jobs', 'overseas_plans', 'overseas_picture_versions', 'overseas_archives',
                 'overseas_skills', 'overseas_settings'):
        assert before[name][0] > 0, 'Backup must include actual complete workflow facts: ' + name
    backup = execute('pg_dump', '-U', 'postgres', '-Fc', '--no-owner', '--no-privileges', 'overseas')
    assert backup.startswith(b'PGDMP')
    target = 'overseas_restore_test'
    execute('createdb', '-U', 'postgres', target)
    try:
        execute('pg_restore', '-U', 'postgres', '--exit-on-error', '--no-owner', '--no-privileges',
                '-d', target, data=backup)
        restored = snapshot(target)
        assert restored == before, 'Restored table contents or sequence positions differ'
        assert snapshot('overseas') == before, 'Source changed during restore drill'
        assert sql('domestic', 'SELECT version_num FROM alembic_version') == domestic
        count = sum(value[0] for name, value in before.items() if not name.startswith('sequence:'))
        print(f'PASS Phase25 pg_dump/pg_restore: {len(before)} tables/sequences, {count} rows, '
              f'{len(backup)} backup bytes; all row hashes and sequence positions match; source unchanged', flush=True)
    finally:
        execute('dropdb', '-U', 'postgres', target)
