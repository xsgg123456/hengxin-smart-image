#!/usr/bin/env python3
"""Selective 245 copy. Run only on the intended host; stdout source is confidential.
Target: run existing Alembic migrations first; only verified pristine migration
seeds may exist. Empty settings seeds are replaced within the import transaction.
Skill reclaim audits omit reviewed business fields; other audits stay unchanged.
"""
import argparse
import json
import re
import subprocess
import sys
import data_policy as policy

SCHEMA = {
    'hengxin': {
        'users': {'id': 'uuid', 'name': 'character varying', 'role': 'character varying', 'status': 'character varying', 'identity_source': 'character varying', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone', 'directory_state': 'character varying'},
        'user_identities': {'id': 'uuid', 'user_id': 'uuid', 'provider': 'character varying', 'corp_id': 'character varying', 'provider_user_id': 'character varying', 'union_id': 'character varying', 'department': 'character varying', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone'},
        'role_assignments': {'id': 'uuid', 'user_id': 'uuid', 'role': 'character varying', 'assigned_by': 'uuid', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone'},
        'domestic_membership_applications': {'id': 'uuid', 'corp_id': 'character varying', 'provider_user_id': 'character varying', 'union_id': 'character varying', 'name': 'character varying', 'department': 'character varying', 'status': 'character varying', 'version': 'integer', 'reason': 'character varying', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone'},
        'domestic_membership_application_events': {'id': 'uuid', 'application_id': 'uuid', 'actor_id': 'uuid', 'action': 'character varying', 'before': 'json', 'after': 'json', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone'},
        'domestic_member_audits': {'id': 'uuid', 'member_id': 'uuid', 'actor_id': 'uuid', 'action': 'character varying', 'before': 'json', 'after': 'json', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone'},
        'system_settings': {'id': 'integer', 'version': 'integer', 'values': 'json', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone'},
        'settings_audit': {'id': 'uuid', 'operator_id': 'uuid', 'operator_name': 'character varying', 'version': 'integer', 'before': 'json', 'after': 'json', 'fields': 'json', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone'},
    },
    'hengxin_overseas': {
        'overseas_members': {'id': 'uuid', 'corp_id': 'character varying', 'provider_user_id': 'character varying', 'union_id': 'character varying', 'name': 'character varying', 'department': 'character varying', 'status': 'character varying', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone', 'version': 'integer', 'directory_state': 'character varying'},
        'overseas_member_roles': {'id': 'uuid', 'user_id': 'uuid', 'role': 'character varying', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone'},
        'overseas_membership_applications': {'id': 'uuid', 'corp_id': 'character varying', 'provider_user_id': 'character varying', 'union_id': 'character varying', 'name': 'character varying', 'department': 'character varying', 'status': 'character varying', 'version': 'integer', 'reason': 'character varying', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone'},
        'overseas_membership_application_events': {'id': 'uuid', 'application_id': 'uuid', 'actor_id': 'uuid', 'action': 'character varying', 'before': 'json', 'after': 'json', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone'},
        'overseas_member_audits': {'id': 'uuid', 'member_id': 'uuid', 'actor_id': 'uuid', 'action': 'character varying', 'before': 'json', 'after': 'json', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone'},
        'overseas_settings': {'id': 'integer', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone', 'version': 'integer', 'values': 'json'},
        'overseas_installed_skill_availability': {'id': 'character varying', 'enabled': 'boolean', 'version': 'integer', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone', 'platforms': 'json'},
        'overseas_management_audit': {'id': 'uuid', 'created_at': 'timestamp with time zone', 'updated_at': 'timestamp with time zone', 'actor_id': 'uuid', 'action': 'character varying', 'target': 'character varying', 'before': 'json', 'after': 'json'},
    },
}
ALL_TABLES = {
    'hengxin': 'alembic_version api_edit_conversations api_edit_events api_edit_turns api_image_attempts api_image_channel api_image_dispatch api_image_files api_image_items api_image_operations api_image_tasks api_image_versions api_task_deletions api_usage_facts api_worker_heartbeats auth_login_states auth_sessions capacity_gate capacity_reservations cli_retention cli_retention_object_links cli_retention_objects cli_retention_records cli_retention_runs cli_retention_service cli_retention_totals domestic_member_audits domestic_membership_application_events domestic_membership_applications execution_gate image_variants job_outbox job_records role_assignments settings_audit system_settings user_identities users worker_heartbeats'.split(),
    'hengxin_overseas': 'overseas_alembic_version overseas_archive_assets overseas_archive_deletions overseas_archive_events overseas_archives overseas_draft_imports overseas_draft_materials overseas_execution_events overseas_execution_gate overseas_execution_objects overseas_installed_skill_availability overseas_job_outbox overseas_jobs overseas_management_audit overseas_material_versions overseas_materials overseas_member_audits overseas_member_roles overseas_members overseas_membership_application_events overseas_membership_applications overseas_picture_versions overseas_pictures overseas_plans overseas_requirement_drafts overseas_requirements_reviews overseas_sessions overseas_settings overseas_skill_versions overseas_skills overseas_studio_conversation_deletions overseas_studio_conversations overseas_studio_material_visibility overseas_studio_output_files overseas_studio_pictures overseas_studio_transcript overseas_studio_turns overseas_studio_uploads overseas_task_deletions overseas_task_events overseas_task_outbox overseas_task_requests overseas_task_skus overseas_tasks'.split(),
}

VERSIONS = {'hengxin': ('alembic_version', '0032'),
            'hengxin_overseas': ('overseas_alembic_version', 'overseas_0026')}
SEEDS = {
    'execution_gate': {'id': 1}, 'overseas_execution_gate': {'id': 1, 'paused': False},
    'capacity_gate': dict(id=1, enabled=False, floor_bytes=0, api_bytes=0, cli_bytes=0,
                          free_bytes=0, sample_at=None, volumes={}),
    'api_image_channel': dict(id=1, paused=False, reason=None, item_id=None, token=None,
        lease_until=None, next_send_at=None, cooldown_until=None, failure_streak=0,
        generation=0, probe_attempt_id=None, recovering=False, recovery_limit=1),
    'cli_retention_totals': dict(id='api_cli', cache_total=0, history_total=0),
    'system_settings': dict(id=1, version=1, values={}),
    'overseas_settings': dict(id=1, version=1, values={}),
}


def literal(value):
    """Hex avoids SQL quoting and psql metacommand injection, retaining JSON numbers."""
    return "convert_from(decode('%s','hex'),'UTF8')" % value.encode('utf-8').hex()


def ident(value):
    if not re.fullmatch(r'[a-z_][a-z_0-9]*', value):
        raise ValueError('invalid identifier')
    return '"' + value + '"'


def assertion(condition, message):
    return f"IF ({condition}) IS NOT TRUE THEN RAISE EXCEPTION '{message}'; END IF;\n"


def schema_guard(db):
    schema = SCHEMA[db]
    names = ','.join("'" + n + "'" for n in sorted(ALL_TABLES[db]))
    checks = assertion("(SELECT array_agg(tablename::text ORDER BY tablename) "
                       "FROM pg_tables WHERE schemaname='public') = "
                       f"ARRAY[{names}]", 'table inventory mismatch')
    for table, columns in schema.items():
        expected = literal(json.dumps(columns)) + '::jsonb'
        checks += assertion("(SELECT jsonb_object_agg(column_name,data_type) FROM "
                            "information_schema.columns WHERE table_schema='public' "
                            f"AND table_name='{table}') = {expected}", 'column mismatch: ' + table)
        checks += assertion("EXISTS (SELECT 1 FROM pg_constraint WHERE "
                            f"conrelid='public.{table}'::regclass AND contype='p' "
                            "AND conkey=ARRAY[(SELECT attnum FROM pg_attribute WHERE "
                            f"attrelid='public.{table}'::regclass AND attname='id')])",
                            'primary key mismatch: ' + table)
    version_table, version = VERSIONS[db]
    checks += assertion(f"(SELECT array_agg(version_num::text) FROM public.{version_table}) "
                        f"= ARRAY['{version}']", 'migration version mismatch')
    checks += assertion("NOT EXISTS (SELECT 1 FROM pg_constraint c JOIN pg_class t "
                        "ON c.conrelid=t.oid JOIN pg_namespace n ON t.relnamespace=n.oid "
                        "WHERE n.nspname='public' AND NOT c.convalidated)", 'unvalidated constraint')
    checks += assertion("NOT EXISTS (SELECT 1 FROM pg_class t JOIN pg_namespace n "
                        "ON t.relnamespace=n.oid WHERE n.nspname='public' AND t.relrowsecurity)",
                        'row security enabled')
    checks += assertion("NOT EXISTS (SELECT 1 FROM pg_trigger g JOIN pg_class t ON "
                        "g.tgrelid=t.oid JOIN pg_namespace n ON t.relnamespace=n.oid "
                        "WHERE n.nspname='public' AND g.tgisinternal AND g.tgenabled NOT IN ('O','A'))",
                        'disabled constraint trigger')
    positions = literal(json.dumps({t: i for i, t in enumerate(schema)})) + '::jsonb'
    checks += assertion("NOT EXISTS (SELECT 1 FROM pg_constraint c JOIN pg_class t ON c.conrelid=t.oid "
                        "JOIN pg_class r ON c.confrelid=r.oid WHERE c.contype='f' AND "
                        f"{positions} ? t.relname AND (NOT {positions} ? r.relname OR "
                        f"({positions}->>t.relname)::int <= ({positions}->>r.relname)::int))",
                        'foreign key import order mismatch')
    return 'DO $guard$ BEGIN\n' + checks + 'END $guard$;\n'


def rows_query(db, table, filtered=True):
    columns = ','.join(policy.project_column(c) if filtered and table == 'overseas_management_audit'
                       else ident(c) for c in SCHEMA[db][table])
    where = " WHERE action LIKE 'skill.%'" if filtered and table == 'overseas_management_audit' else ''
    return ("SELECT COALESCE(jsonb_agg(to_jsonb(r) ORDER BY r.id), '[]'::jsonb) "
            f'FROM (SELECT {columns} FROM public.{ident(table)}{where}) r')


def digest_sql(expression):
    return f"encode(sha256(convert_to(({expression})::text,'UTF8')),'hex')"


def envelope_sql(db):
    pairs = []
    for table in SCHEMA[db]:
        rows = '(' + rows_query(db, table) + ')'
        pairs += [f"'{table}',jsonb_build_object('rows',{rows},'count',jsonb_array_length({rows}),"
                  f"'sha256',{digest_sql(rows)})"]
    return ("SELECT jsonb_build_object('format',1,'database',current_database(),"
            f"'migration_version','{VERSIONS[db][1]}',"
            "'snapshot_at',transaction_timestamp(),'snapshot',pg_current_snapshot()::text,"
            f"'audit_policy','{policy.POLICY}','audit_transformations',{policy.report_sql(db)},'tables',jsonb_build_object("
            + ','.join(pairs) + '));\n')


def source_sql(db):
    return ("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n"
            "SET LOCAL statement_timeout='120s'; SET LOCAL lock_timeout='5s';\n"
            "SET LOCAL idle_in_transaction_session_timeout='150s'; SET LOCAL timezone='UTC';\n"
            + schema_guard(db) + policy.source_guard(db) + envelope_sql(db) + 'COMMIT;\n')


def validate(raw, db):
    data = json.loads(raw)
    if (data.get('format') != 1 or data.get('database') != db or
            data.get('migration_version') != VERSIONS[db][1] or
            data.get('audit_policy') != policy.POLICY or
            set(data.get('tables', {})) != set(SCHEMA[db])):
        raise ValueError('export envelope mismatch')
    for table, info in data['tables'].items():
        rows = info['rows']
        if not isinstance(rows, list) or info['count'] != len(rows):
            raise ValueError('count mismatch: ' + table)
        if not re.fullmatch('[a-f0-9]{64}', info['sha256']):
            raise ValueError('invalid digest: ' + table)
        for row in rows:
            if set(row) != set(SCHEMA[db][table]):
                raise ValueError('row columns mismatch: ' + table)
            if table == 'overseas_management_audit':
                policy.validate_row(row)
    audit_rows = data['tables'].get('overseas_management_audit', {}).get('rows', [])
    policy.validate_report(data.get('audit_transformations'), audit_rows)
    return data


def target_sql(db, raw):
    validate(raw, db)
    version_table = VERSIONS[db][0]
    sql = ("BEGIN; SET LOCAL statement_timeout='120s'; SET LOCAL lock_timeout='5s';\n"
           "SET LOCAL timezone='UTC'; SET LOCAL session_replication_role='origin';\n")
    sql += 'LOCK TABLE ' + ','.join('public.' + ident(t) for t in ALL_TABLES[db]) + ' IN ACCESS EXCLUSIVE MODE;\n'
    sql += schema_guard(db)
    checks = ''
    for t in ALL_TABLES[db]:
        if t == version_table:
            continue
        condition = f'NOT EXISTS (SELECT FROM public.{ident(t)})'
        if t in SEEDS:
            ignored = "ARRAY['created_at','updated_at','since']" if t == 'cli_retention_totals' else "ARRAY['created_at','updated_at']"
            condition = (f'(SELECT count(*) FROM public.{ident(t)}) <= 1 AND NOT EXISTS '
                         f'(SELECT FROM public.{ident(t)} r WHERE to_jsonb(r)-{ignored} '
                         f'<> {literal(json.dumps(SEEDS[t]))}::jsonb)')
        if t == 'overseas_installed_skill_availability':
            expected = literal(json.dumps(policy.INSTALLED_SKILL_SEEDS)) + '::jsonb'
            condition += (f' OR ((SELECT jsonb_agg(to_jsonb(r)-ARRAY[\'created_at\',\'updated_at\'] '
                          f'ORDER BY r.id) FROM public.{ident(t)} r) = {expected} AND NOT EXISTS '
                          f'(SELECT FROM public.{ident(t)} WHERE (created_at IS NOT NULL AND '
                          "updated_at IS NOT NULL AND created_at >= transaction_timestamp()-INTERVAL '24 hours' "
                          "AND updated_at >= created_at AND updated_at <= transaction_timestamp()+INTERVAL '5 minutes') "
                          'IS NOT TRUE))')
        checks += assertion(condition, 'target not empty: ' + t)
    sql += 'DO $empty$ BEGIN\n' + checks + 'END $empty$;\n'
    for t in SCHEMA[db]:
        if t in ('system_settings', 'overseas_settings'):
            sql += f'DELETE FROM public.{ident(t)};\n'  # Only the checked empty seed.
        if t == 'overseas_installed_skill_availability':
            sql += (f'DELETE FROM public.{ident(t)} WHERE id=ANY('
                    + policy.sql_keys(policy.INSTALLED_SKILL_INITIAL) + ');\n')
    sql += 'CREATE TEMP TABLE migration_payload(data jsonb) ON COMMIT DROP;\n'
    sql += 'INSERT INTO migration_payload VALUES (' + literal(raw) + '::jsonb);\n'
    for table, columns in SCHEMA[db].items():
        cols = ','.join(ident(c) for c in columns)
        sql += (f'INSERT INTO public.{ident(table)} ({cols}) SELECT {cols} FROM '
                f"jsonb_populate_recordset(NULL::public.{ident(table)},"
                f"(SELECT data->'tables'->'{table}'->'rows' FROM migration_payload));\n")
    sql += 'SET CONSTRAINTS ALL IMMEDIATE;\n'
    checks = ''
    for table in SCHEMA[db]:
        ref = f"(SELECT data->'tables'->'{table}' FROM migration_payload)"
        checks += assertion(f"({rows_query(db, table, False)}) = {ref}->'rows' AND "
                            f"{digest_sql('(' + rows_query(db, table, False) + ')')} = {ref}->>'sha256' AND "
                            f"(SELECT count(*) FROM public.{ident(table)}) = ({ref}->>'count')::bigint",
                            'post-import mismatch: ' + table)
    sql += 'DO $verify$ BEGIN\n' + checks + 'END $verify$;\nCOMMIT;\n'
    return sql


def command(container, db, user, target=False, confirmation=None):
    if not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]*', container) or not re.fullmatch('[a-zA-Z0-9_]+', user):
        raise ValueError('invalid local container/user')
    if db not in SCHEMA:
        raise ValueError('database not allowed')
    if target and (not re.fullmatch(r'hengxin-lan-[a-z0-9][a-z0-9-]*', container)
                   or confirmation != container + '/' + db):
        raise ValueError('explicit new target confirmation required')
    return ['docker', '--host', 'unix:///var/run/docker.sock', 'exec', '-i', container,
            'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-h', '/var/run/postgresql',
            '-U', user, '-d', db, '-f', '-']


def run(cmd, sql):
    result = subprocess.run(cmd, input=sql, text=True, encoding='utf-8',
                            capture_output=True, timeout=180, check=False)
    if result.returncode:
        # PostgreSQL error details can contain SQL/data: never echo captured stderr.
        blocked = re.search(r'ERROR:\s+target not empty: ([a-z_]+)', result.stderr)
        if blocked and blocked[1] in {t for names in ALL_TABLES.values() for t in names}:
            raise RuntimeError('target not empty: ' + blocked[1])
        raise RuntimeError('database operation failed; success not confirmed; details withheld')
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('source', 'target'))
    parser.add_argument('--container', required=True)
    parser.add_argument('--database', choices=tuple(SCHEMA), required=True)
    parser.add_argument('--user', default='hengxin')
    parser.add_argument('--confirm-target')
    args = parser.parse_args()
    cmd = command(args.container, args.database, args.user, args.mode == 'target', args.confirm_target)
    if args.mode == 'source':
        if sys.stdout.isatty():
            raise ValueError('source stdout must be a protected pipe/file')
        raw = run(cmd, source_sql(args.database))
        validate(raw, args.database)
        print(raw)
    else:
        raw = sys.stdin.read(64 * 1024 * 1024 + 1)
        if len(raw) > 64 * 1024 * 1024:
            raise ValueError('payload exceeds limit')
        data = validate(raw, args.database)
        run(cmd, target_sql(args.database, raw))
        print(json.dumps({'database': args.database, 'audit_policy': policy.POLICY,
                          'audit_transformations': data['audit_transformations'], 'tables': {
            t: {k: v[k] for k in ('count', 'sha256')} for t, v in data['tables'].items()}}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print('copy aborted: ' + (str(exc) if isinstance(exc, (ValueError, RuntimeError))
                                 else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
