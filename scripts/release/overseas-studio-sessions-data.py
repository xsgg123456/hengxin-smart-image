"""Read-only migration invariants: compare original fields, verify new values separately."""
import json
import re

TABLE = 'overseas_studio_conversation_deletions'
ADDED = {
    'overseas_studio_conversations': {'name', 'version'},
    'overseas_studio_uploads': {'conversation_id'},
    'overseas_task_requests': {'conversation_id'},
    'overseas_archive_assets': {'source_conversation_id', 'source_conversation_name'},
    'overseas_studio_material_visibility': {'scope'},
    'overseas_studio_pictures': {'origin_turn_id'},
}


def identifier(value):
    assert re.fullmatch(r'[a-z][a-z0-9_]*', value), 'Unsafe SQL identifier'
    return '"' + value + '"'


def tables(sql):
    return sql("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()


def original_rows(sql):
    result = {}
    for name in tables(sql):
        if name in (TABLE, 'overseas_alembic_version'):
            continue
        table = identifier(name)
        row = 'to_jsonb(t)' + ''.join("-'" + key + "'" for key in sorted(ADDED.get(name, ())))
        result[name] = sql(f"SELECT count(*)||':'||md5(coalesce(string_agg(md5(({row})::text),'' "
                           f"ORDER BY ({row})::text),'')) FROM public.{table} t")
    return result


def columns(sql):
    return json.loads(sql("SELECT coalesce(json_agg(c ORDER BY table_name,ordinal_position),'[]') "
                         "FROM information_schema.columns c WHERE table_schema='public'"))


def original_columns(rows):
    result = []
    for row in rows:
        name, column = row['table_name'], row['column_name']
        if name == TABLE or column in ADDED.get(name, ()):
            continue
        entry = dict(row)
        # This approved nullable change keeps referenced image snapshots after deletion.
        if name == 'overseas_studio_pictures' and column == 'turn_id':
            entry['is_nullable'] = 'YES'
        result.append(entry)
    return result


def before(sql):
    names, fields = set(tables(sql)), columns(sql)
    assert TABLE not in names, 'Session deletion table already exists'
    assert not any(c['column_name'] in ADDED.get(c['table_name'], ()) for c in fields), 'Session columns already exist'
    return dict(tables=sorted(names), columns=original_columns(fields), rows=original_rows(sql))


def verify(sql, baseline):
    assert set(tables(sql)) == set(baseline['tables']) | {TABLE}, 'Unexpected migrated table set'
    fields = columns(sql)
    assert original_columns(fields) == baseline['columns'], 'Existing column definition changed'
    assert original_rows(sql) == baseline['rows'], 'Original business data changed'
    actual = {(c['table_name'], c['column_name']) for c in fields}
    assert all((table, column) in actual for table, names in ADDED.items() for column in names), 'Missing session columns'
    assert next(c for c in fields if c['table_name'] == 'overseas_studio_pictures'
                and c['column_name'] == 'turn_id')['is_nullable'] == 'YES', 'Picture snapshot nullable migration missing'
    assert sql('SELECT count(*) FROM ' + TABLE) == '0', 'Migration unexpectedly created deletions'
    for table, column in [('overseas_studio_uploads', 'conversation_id'),
                          ('overseas_task_requests', 'conversation_id'),
                          ('overseas_studio_pictures', 'origin_turn_id')]:
        assert sql(f'SELECT count(*) FROM {identifier(table)} WHERE {identifier(column)} IS NOT NULL') == '0', 'Historical ownership changed'
    assert sql("SELECT count(*) FROM overseas_studio_material_visibility WHERE scope IS DISTINCT FROM ''") == '0', 'Historical visibility changed'
    assert sql("""WITH numbered AS (SELECT id, row_number() OVER
        (PARTITION BY task_id ORDER BY created_at,id) AS n FROM overseas_studio_conversations)
        SELECT count(*) FROM overseas_studio_conversations c JOIN numbered n USING(id)
        WHERE c.version IS DISTINCT FROM 1 OR c.name IS DISTINCT FROM ('会话 ' || n.n::text)""") == '0', 'Conversation names/version backfill differs'
    assert sql("""SELECT count(*) FROM overseas_archive_assets a
        LEFT JOIN overseas_studio_pictures p ON a.source_version='studio:' || p.id::text
        LEFT JOIN overseas_studio_turns t ON t.id=p.turn_id
        LEFT JOIN overseas_studio_conversations c ON c.id=t.conversation_id
        WHERE a.source_conversation_id IS DISTINCT FROM c.id
           OR a.source_conversation_name IS DISTINCT FROM c.name""") == '0', 'Archive source snapshot differs'
    assert sql("""SELECT count(*) FROM pg_constraint c JOIN pg_class t ON c.conrelid=t.oid
        JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname='public' AND t.relname='overseas_studio_material_visibility' AND c.contype='u'
          AND pg_get_constraintdef(c.oid)='UNIQUE (task_id, checksum, scope)'""") == '1', 'Scoped visibility uniqueness missing'
    assert sql("""SELECT count(*) FROM pg_constraint c JOIN pg_class t ON c.conrelid=t.oid
        JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname='public' AND t.relname='overseas_studio_material_visibility' AND c.contype='u'
          AND pg_get_constraintdef(c.oid)='UNIQUE (task_id, checksum)'""") == '0', 'Old visibility uniqueness remains'
