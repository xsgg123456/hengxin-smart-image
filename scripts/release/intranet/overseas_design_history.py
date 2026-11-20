"""Private backup and aggregate evidence for the overseas 0026 -> 0028 migration."""
import json

import operations
import snapshot

TITLES = {'overseas_tasks': 'name', 'overseas_archives': 'task_name'}
HISTORY = (*TITLES, 'overseas_task_skus', 'overseas_archive_assets')
FEEDBACK = ('overseas_feedback', 'overseas_feedback_grants')


def sql(u, query):
    name, user, database = snapshot.database(u, 'overseas')
    return u.run(['docker', 'exec', name, 'psql', '-X', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
                  '-U', user, '-d', database, '-c', query], timeout=300).strip()


def backup(u, descriptor):
    report = u.WORK / 'data-backup/verified.json'
    if not report.exists():
        operations.backup(u, u.WORK, scope='overseas', pass_fds=(descriptor,))
    u.safe(report)
    archive = report.parent / 'overseas.dump'
    u.safe(archive)
    size = archive.stat().st_size
    if not size or json.loads(report.read_bytes()) != {
            'overseas': {'bytes': size, 'sha256': operations.file_sha(archive)}}:
        raise RuntimeError('Overseas database backup receipt differs from archive')
    return u.digest(report.read_bytes())


def rows(u):
    result = {}
    for table in HISTORY:
        # design_type is the sole new column on two legacy tables. The rest of
        # each row and all SKU/asset associations must survive byte for byte.
        projection = "to_jsonb(t) - 'design_type'" if table in TITLES else 'to_jsonb(t)'
        result[table] = json.loads(sql(u, f"""
            SELECT json_build_array(count(*), encode(sha256(convert_to(
                coalesce(string_agg(h, '' ORDER BY h), ''), 'UTF8')), 'hex'))
            FROM (SELECT encode(sha256(convert_to(({projection})::text, 'UTF8')), 'hex') AS h
                  FROM public.{table} AS t) AS fingerprints
        """))
    return result


def check_shape(u, migrated):
    for table, title in TITLES.items():
        columns = sql(u, f"""
            SELECT json_build_array(column_name, data_type, character_maximum_length, is_nullable, column_default)
            FROM information_schema.columns WHERE table_schema='public' AND table_name='{table}'
            AND column_name IN ('{title}', 'design_type')
        """)
        found = {name: rest for name, *rest in map(json.loads, columns.splitlines())}
        expected = {title: ['character varying', 161 if migrated else 80,
                            'NO' if table == 'overseas_tasks' else 'YES', None]}
        if migrated:
            expected['design_type'] = ['character varying', 20, 'NO', "'platform'::character varying"]
        if found != expected:
            raise RuntimeError('Overseas design column definition differs: ' + table)
        if migrated and sql(u, f"SELECT count(*) FROM public.{table} WHERE design_type IS DISTINCT FROM 'platform'") != '0':
            raise RuntimeError('Legacy design type differs: ' + table)
    for table in FEEDBACK:
        present = sql(u, f"SELECT to_regclass('public.{table}') IS NOT NULL")
        if present != ('t' if migrated else 'f'):
            raise RuntimeError('Unexpected feedback table state: ' + table)
        if migrated and sql(u, f'SELECT count(*) FROM public.{table}') != '0':
            raise RuntimeError('Unexpected feedback rows before opening ingress')
    if migrated:
        indexes = sql(u, """SELECT indexname FROM pg_indexes WHERE schemaname='public'
            AND tablename='overseas_feedback' AND indexname IN ('ix_overseas_feedback_owner_date',
            'ix_overseas_feedback_status_date') ORDER BY indexname""").splitlines()
        if indexes != ['ix_overseas_feedback_owner_date', 'ix_overseas_feedback_status_date']:
            raise RuntimeError('Overseas feedback indexes missing')
        # Real API users need DML rights but may never change migration history.
        rights = sql(u, """SELECT
            has_table_privilege('overseas_app', 'public.overseas_feedback', 'SELECT')
            AND has_table_privilege('overseas_app', 'public.overseas_feedback', 'INSERT')
            AND has_table_privilege('overseas_app', 'public.overseas_feedback', 'UPDATE')
            AND has_table_privilege('overseas_app', 'public.overseas_feedback_grants', 'SELECT')
            AND has_table_privilege('overseas_app', 'public.overseas_feedback_grants', 'INSERT')
            AND has_table_privilege('overseas_app', 'public.overseas_feedback_grants', 'DELETE')
            AND NOT has_table_privilege('overseas_app', 'public.overseas_alembic_version', 'INSERT,UPDATE,DELETE')
        """)
        if rights != 't':
            raise RuntimeError('Overseas feedback or schema history role grants differ')


def capture(u):
    check_shape(u, migrated=False)
    # Catch missing owner defaults before the non-reversible 0028 DDL commits.
    grants = sql(u, """SELECT DISTINCT acl.privilege_type
        FROM pg_default_acl AS d CROSS JOIN LATERAL aclexplode(d.defaclacl) AS acl
        WHERE d.defaclrole=(SELECT relowner FROM pg_class WHERE oid='public.overseas_tasks'::regclass)
        AND d.defaclobjtype='r' AND d.defaclnamespace IN (0, 'public'::regnamespace)
        AND acl.grantee='overseas_app'::regrole""").splitlines()
    if not {'SELECT', 'INSERT', 'UPDATE', 'DELETE'} <= set(grants):
        raise RuntimeError('Overseas application lacks default grants for new feedback tables')
    return rows(u)


def verify(u, expected):
    check_shape(u, migrated=True)
    if set(expected) != set(HISTORY) or rows(u) != expected:
        raise RuntimeError('Overseas task/SKU/archive history differs after migration')
