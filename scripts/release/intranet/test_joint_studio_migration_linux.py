"""Rehearse backup/restore and transactional schema upgrade on disposable local databases."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.mark.skipif(not os.environ.get('TEST_DOMESTIC_STUDIO_DATABASE_URL') or not shutil.which('pg_dump')
                    or not shutil.which('pg_restore'), reason='requires isolated local PostgreSQL tools')
def test_backup_restore_and_failed_then_successful_upgrade(tmp_path):
    url = make_url(os.environ['TEST_DOMESTIC_STUDIO_DATABASE_URL'])
    if (url.drivername != 'postgresql+psycopg' or url.host not in ('127.0.0.1', 'localhost')
            or not (url.database or '').endswith('_test')):
        pytest.fail('Only a disposable local *_test database may run this rehearsal')
    backend = Path(__file__).resolve().parents[3] / 'hengxin-smart-image/backend'
    names = ['hx_studio_rehearsal_' + uuid4().hex + '_test' for _ in range(2)]
    admin = create_engine(url, isolation_level='AUTOCOMMIT')
    created = []

    def dburl(name):
        return url.set(database=name).render_as_string(hide_password=False)

    def command(name, revision, expected=0):
        env = dict(os.environ, HX_BUSINESS_CONTEXT='domestic', APP_ENV='test',
                   DATABASE_URL=dburl(name), MINIO_ACCESS_KEY='test-access', MINIO_SECRET_KEY='test-secret',
                   DOMESTIC_STUDIO_MIGRATION_FENCE='1')
        result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', revision],
                                cwd=backend, env=env, capture_output=True, timeout=120)
        assert (result.returncode == 0) == (expected == 0), result.stderr.decode(errors='replace')
        if expected:
            assert b'Existing conversation deletion table requires manual verification' in result.stderr

    try:
        with admin.connect() as connection:
            for name in names:
                connection.execute(text('CREATE DATABASE "' + name + '"'))
                created.append(name)
        command(names[0], '0032')
        source = create_engine(dburl(names[0]))
        with source.begin() as connection:
            connection.execute(text('CREATE TABLE rehearsal_preserved (value text NOT NULL)'))
            connection.execute(text("INSERT INTO rehearsal_preserved VALUES ('old user data')"))
        source.dispose()
        dump = tmp_path / 'domestic.dump'
        database_args = ['-h', url.host, '-p', str(url.port or 5432), '-U', url.username or 'postgres']
        with dump.open('wb') as stream:
            subprocess.run(['pg_dump', *database_args, '-Fc', names[0]], stdout=stream,
                           stderr=subprocess.PIPE, check=True, timeout=120)
        subprocess.run(['pg_restore', '--list', str(dump)], capture_output=True, check=True, timeout=120)
        subprocess.run(['pg_restore', *database_args, '--no-owner', '--no-acl', '-d', names[1], str(dump)],
                       capture_output=True, check=True, timeout=120)
        restored = create_engine(dburl(names[1]))
        try:
            with restored.begin() as connection:
                connection.execute(text('CREATE TABLE domestic_studio_conversation_deletions (conflict int)'))
            command(names[1], '0043', expected=1)
            with restored.begin() as connection:
                assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0032'
                assert connection.scalar(text("SELECT to_regclass('domestic_studio_skill_bindings')")) is None
                assert connection.scalar(text('SELECT value FROM rehearsal_preserved')) == 'old user data'
                connection.execute(text('DROP TABLE domestic_studio_conversation_deletions'))
            command(names[1], '0043')
            with restored.connect() as connection:
                assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0043'
                assert connection.scalar(text('SELECT count(*) FROM domestic_studio_skill_bindings')) == 0
                assert connection.scalar(text("SELECT column_default FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'domestic_studio_turns' "
                    "AND column_name = 'output_intents'")) is not None
                assert connection.scalar(text('SELECT value FROM rehearsal_preserved')) == 'old user data'
                assert connection.scalar(text("SELECT to_regclass('overseas_alembic_version')")) is None
        finally:
            restored.dispose()
    finally:
        with admin.connect() as connection:
            for name in reversed(created):
                connection.execute(text('DROP DATABASE "' + name + '"'))
        admin.dispose()
