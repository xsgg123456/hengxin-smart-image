"""Validate the five CHECK predicates and retain only aggregate historical evidence."""
import json
import re

from domestic_tasks_history import sql

TABLES = {'domestic_studio_skill_bindings', 'domestic_studio_workspaces',
          'domestic_studio_tasks', 'domestic_studio_conversations', 'domestic_studio_archives'}
OLD_PRODUCTS = {'camera', 'case'}
NEW_PRODUCTS = {'film', 'cable', 'earbud', 'accessory'}
OLD_REPLACEMENTS = {'product', 'scene', 'phone'}


def check_constraints(u, expanded):
    records = sql(u, """
        SELECT json_build_array(t.relname, c.conname, c.convalidated, pg_get_expr(c.conbin, c.conrelid))
        FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attname = 'workspace' AND a.attnum = ANY(c.conkey)
        WHERE n.nspname = 'public' AND c.contype = 'c' AND t.relname LIKE 'domestic_studio_%'
    """)
    seen = set()
    for line in records.splitlines():
        table, name, valid, expression = json.loads(line)
        if table not in TABLES or table in seen or name != table + '_workspace_check' or not valid:
            raise RuntimeError('Unexpected domestic workspace CHECK identity')
        # pg_get_expr deparses varchar IN (...) as a text equality with ANY(ARRAY[...]).
        match = re.fullmatch(
            r"\(\(workspace\)::text = ANY \(\(ARRAY\[('[a-z]+'::character varying"
            r"(?:, '[a-z]+'::character varying)*)\]\)::text\[\]\)\)", expression)
        expected = OLD_PRODUCTS | (NEW_PRODUCTS if expanded else set())
        if table != 'domestic_studio_archives':
            expected |= OLD_REPLACEMENTS | ({'edit'} if expanded else set())
        if not match or sorted(re.findall(r"'([a-z]+)'", match[1])) != sorted(expected):
            raise RuntimeError('Unexpected domestic workspace CHECK values on ' + table)
        seen.add(table)
    if seen != TABLES:
        raise RuntimeError('Missing domestic workspace CHECK')


def rows(u):
    tables = sql(u, "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename LIKE 'domestic_studio_%' ORDER BY tablename").splitlines()
    if not TABLES.issubset(tables):
        raise RuntimeError('Missing domestic workspace table')
    result = {}
    for table in tables:
        if not re.fullmatch(r'domestic_studio_[a-z_]+', table):
            raise RuntimeError('Unexpected domestic workspace table name')
        raw = sql(u, """
            SELECT json_build_array(count(*), encode(sha256(convert_to(
                coalesce(string_agg(digest, '' ORDER BY digest), ''), 'UTF8')), 'hex'))
            FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text, 'UTF8')), 'hex') AS digest
                  FROM public.""" + table + " AS t) AS rows")
        result[table] = json.loads(raw)
    return result


def capture(u):
    check_constraints(u, expanded=False)
    return rows(u)


def verify(u, expected):
    check_constraints(u, expanded=True)
    if rows(u) != expected:
        raise RuntimeError('Domestic historical rows changed during workspace migration')
