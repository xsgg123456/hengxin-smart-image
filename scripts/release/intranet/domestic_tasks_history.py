"""Read-only database evidence without printing user rows or credentials."""
import hashlib
import json
import re

import snapshot

NEW_TABLES = {'domestic_studio_tasks', 'domestic_studio_task_requests'}


def sql(u, query):
    name, user, db = snapshot.database(u, 'domestic')
    return u.run(['docker', 'exec', name, 'psql', '-X', '-A', '-t',
                  '-v', 'ON_ERROR_STOP=1', '-U', user, '-d', db, '-c', query], timeout=120).strip()


def capture(u):
    tables = sql(u, "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                 "AND tablename LIKE 'domestic_studio_%' ORDER BY tablename").splitlines()
    if 'domestic_studio_conversations' not in tables:
        raise RuntimeError('Domestic history table missing')
    result = {}
    for name in tables:
        if not re.fullmatch(r'domestic_studio_[a-z_]+', name):
            raise RuntimeError('Unrecognized domestic history table')
        if name in NEW_TABLES:
            continue
        # jsonb key order is deterministic. Strip only the newly added FK;
        # preserving all original columns also catches changed recovery tokens.
        rows = sql(u, 'SELECT (to_jsonb(t) - \'task_id\')::text FROM public."' + name
                   + '" t ORDER BY (to_jsonb(t) - \'task_id\')::text')
        result[name] = {'rows': len(rows.splitlines()) if rows else 0,
                        'sha256': hashlib.sha256(rows.encode()).hexdigest()}
    return result


def verify(u, expected):
    if capture(u) != expected:
        raise RuntimeError('Domestic historical rows changed during Tasks migration')
    invalid = sql(u, "SELECT count(*) FROM domestic_studio_conversations c "
                  "LEFT JOIN domestic_studio_tasks t ON t.id=c.task_id "
                  "AND t.owner_id=c.owner_id AND t.workspace=c.workspace WHERE t.id IS NULL")
    groups = sql(u, "SELECT count(*) FROM (SELECT owner_id,workspace FROM "
                 "domestic_studio_conversations GROUP BY owner_id,workspace) g")
    tasks = sql(u, 'SELECT count(*) FROM domestic_studio_tasks')
    if invalid != '0' or tasks != groups:
        raise RuntimeError('Historical task ownership/count verification failed')


if __name__ == '__main__':
    import engine
    print(json.dumps({'schema': snapshot.schemas(engine.u), 'history': capture(engine.u)}, sort_keys=True))
