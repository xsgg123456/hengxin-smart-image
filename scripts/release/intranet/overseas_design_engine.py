"""Run the reviewed overseas Alembic revisions under the existing table owner."""
import hashlib
import os
import select
import subprocess
import time

import snapshot

LOCK = 'pg_advisory_xact_lock(15443, 20261120)'
SQL_SHA = 'a9f79e8fa8604502515c36c2aed0e19feff05d29f2461b81de1280a4b4ec67a5'
READY = b'HX_OVERSEAS_OWNER_READY'
SOURCE_CHECK = """DO $guard$
BEGIN
    IF current_database() <> 'hengxin_overseas' OR current_user <> 'overseas_owner' OR
        (SELECT array_agg(version_num::text) FROM overseas_alembic_version)
            IS DISTINCT FROM ARRAY['overseas_0026'] OR
        (SELECT pg_get_userbyid(relowner) FROM pg_class
            WHERE oid = 'overseas_alembic_version'::regclass) <> current_user THEN
        RAISE EXCEPTION 'Unexpected overseas database, owner or schema';
    END IF;
END
$guard$;"""
# Keep this list in lockstep with the approved candidate's overseas Alembic env.py.
MODELS = ('auth.models', 'members.models', 'members.application_models', 'tasks.models',
          'materials.models', 'execution.models', 'plans.models', 'pictures.models',
          'archives.models', 'management.models', 'studio.models', 'drafts.models', 'feedback.models')
VALIDATE = f"""from importlib import import_module
for model in {MODELS!r}:
    import_module('app.overseas.' + model)
from app.overseas.db import get_engine, require_overseas_context, validate_migration_database
require_overseas_context()
with get_engine().connect() as connection:
    connection.exec_driver_sql("SET TRANSACTION READ ONLY")
    validate_migration_database(connection)
"""


def psql(u):
    container, user, database = snapshot.database(u, 'overseas')
    if (container, user, database) != ('hengxin-lan-overseas-postgres', 'postgres', 'hengxin_overseas'):
        raise RuntimeError('Unrecognized overseas database maintenance identity')
    return ['docker', 'exec', '-i', container, 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1',
            '-U', user, '-d', database]


def wait_database(u):
    # A migration that received DDL already holds this lock. If its client
    # died before the readiness handshake its process cannot receive DDL.
    u.run([*psql(u), '-c', f"SET statement_timeout='25s'; SELECT {LOCK}"], timeout=30)


def render(u, worker, policy, release=None):
    cwd = str((release or u.RELEASE) / 'backend')
    u.native_run(worker, code=VALIDATE, cwd=cwd, timeout=30)
    sql = u.native_run(worker, module='alembic',
                       args=('-c', 'alembic.overseas.ini', 'upgrade',
                             f'{policy.SOURCE}:{policy.TARGET}', '--sql'), cwd=cwd)
    sql = sql.replace('\r\n', '\n')
    if hashlib.sha256(sql.encode()).hexdigest() != getattr(policy, 'SQL_SHA', SQL_SHA):
        raise RuntimeError('Generated overseas migration SQL differs from the reviewed revisions')
    return sql.strip().removeprefix('BEGIN;').removesuffix('COMMIT;')


def source_check(policy):
    return SOURCE_CHECK.replace('overseas_0026', policy.SOURCE)


def preflight(u, release, policy):
    worker = u.contexts()['hengxin-overseas-worker']
    render(u, worker, policy, release)
    u.run([*psql(u), '-c', 'BEGIN READ ONLY; SET LOCAL ROLE overseas_owner; ' + source_check(policy) + ' ROLLBACK;'])


def wait_ready(process, timeout=45):
    deadline = time.monotonic() + timeout
    output = b''
    while time.monotonic() < deadline:
        ready, _, _ = select.select([process.stdout], [], [], max(0, deadline - time.monotonic()))
        if not ready:
            break
        chunk = os.read(process.stdout.fileno(), 4096)
        if not chunk:
            break
        output += chunk
        if READY in output.splitlines():
            return
        if len(output) > 16384:
            break
    raise RuntimeError('Overseas owner transaction readiness was not confirmed')


def run_migration(u, worker, descriptor, policy):
    sql = render(u, worker, policy)
    # Keep a single PostgreSQL transaction through both revisions. The
    # connection uses the database container's local maintenance socket;
    # no privileged DSN or password enters app settings, argv or receipts.
    begin = (f"BEGIN;\nSET LOCAL statement_timeout='240s';\nSELECT {LOCK};\n"
             f"SET LOCAL ROLE overseas_owner;\n{source_check(policy)}\n"
             f"\\echo {READY.decode()}\n")
    final = ("\nREVOKE INSERT, UPDATE, DELETE ON overseas_alembic_version FROM overseas_app;\n"
             "COMMIT;\n")
    with subprocess.Popen(psql(u), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, pass_fds=(descriptor,)) as process:
        try:
            process.stdin.write(begin.encode())
            process.stdin.flush()
            wait_ready(process)
            process.communicate((sql + final).encode(), timeout=300)
            if process.returncode:
                raise RuntimeError('Overseas owner migration failed inside PostgreSQL')
        except BaseException:
            process.kill()
            process.communicate()
            raise
