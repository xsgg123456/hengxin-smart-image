"""Check the 0029 database shape, role grants and pre-existing business rows."""
from overseas_design_history import backup, sql
import json
import re

BINDINGS = 'overseas_tool_skill_bindings'
ADDED = {'overseas_tasks': {'tool_key': 40, 'creator_identity': 20},
         'overseas_archives': {'creator_identity': 20}}
HISTORY = (*ADDED, 'overseas_task_skus', 'overseas_archive_assets', 'overseas_member_roles',
           'overseas_installed_skill_availability')


def rows(u):
    result = {}
    for table in HISTORY:
        projection = 'to_jsonb(t)' + ''.join(" - '" + name + "'" for name in ADDED.get(table, {}))
        result[table] = json.loads(sql(u, f"""
            SELECT json_build_array(count(*), encode(sha256(convert_to(
                coalesce(string_agg(h, '' ORDER BY h), ''), 'UTF8')), 'hex'))
            FROM (SELECT encode(sha256(convert_to(({projection})::text, 'UTF8')), 'hex') AS h
                  FROM public.{table} AS t) AS fingerprints
        """))
    return result


def check_shape(u, migrated):
    for table, expected in ADDED.items():
        names = ','.join("'" + name + "'" for name in expected)
        columns = sql(u, f"""SELECT json_build_array(column_name, data_type, character_maximum_length,
            is_nullable, column_default) FROM information_schema.columns WHERE table_schema='public'
            AND table_name='{table}' AND column_name IN ({names})""")
        found = {name: rest for name, *rest in map(json.loads, columns.splitlines())}
        if found != ({n: ['character varying', size, 'YES', None] for n, size in expected.items()} if migrated else {}):
            raise RuntimeError('Unexpected workbench metadata columns: ' + table)
        if migrated and sql(u, f'SELECT count(*) FROM public.{table} WHERE ' +
                            ' OR '.join(n + ' IS NOT NULL' for n in expected)) != '0':
            raise RuntimeError('Unexpected historical workbench metadata')
    present = sql(u, f"SELECT to_regclass('public.{BINDINGS}') IS NOT NULL")
    if present != ('t' if migrated else 'f'):
        raise RuntimeError('Unexpected binding table state')
    constraint = sql(u, """SELECT pg_get_constraintdef(oid) FROM pg_constraint
        WHERE conrelid='public.overseas_member_roles'::regclass
        AND conname='ck_overseas_member_roles_role' AND contype='c' AND convalidated""")
    expected_roles = {'designer', 'design_manager', 'super_admin'}
    if migrated:
        expected_roles.add('non_designer')
    if set(re.findall(r"'([^']+)'", constraint)) != expected_roles:
        raise RuntimeError('Unexpected overseas member roles constraint')
    if migrated:
        if sql(u, f'SELECT count(*) FROM public.{BINDINGS}') != '0':
            raise RuntimeError('Bindings must start empty')
        grants = sql(u, f"""SELECT has_table_privilege('overseas_app','public.{BINDINGS}','SELECT')
            AND has_table_privilege('overseas_app','public.{BINDINGS}','INSERT')
            AND has_table_privilege('overseas_app','public.{BINDINGS}','DELETE')
            AND NOT has_table_privilege('overseas_app','public.overseas_alembic_version','INSERT,UPDATE,DELETE')""")
        if grants != 't':
            raise RuntimeError('Unexpected overseas application grants')
    else:
        grants = sql(u, """SELECT DISTINCT acl.privilege_type FROM pg_default_acl AS d
            CROSS JOIN LATERAL aclexplode(d.defaclacl) AS acl
            WHERE d.defaclrole='overseas_owner'::regrole AND d.defaclobjtype='r'
            AND d.defaclnamespace IN (0, 'public'::regnamespace) AND acl.grantee='overseas_app'::regrole""")
        if not {'SELECT','INSERT','UPDATE','DELETE'} <= set(grants.splitlines()):
            raise RuntimeError('Missing overseas default grants')


def capture(u):
    check_shape(u, False)
    return rows(u)


def verify(u, expected):
    check_shape(u, True)
    if rows(u) != expected:
        raise RuntimeError('Historical overseas business rows changed')
