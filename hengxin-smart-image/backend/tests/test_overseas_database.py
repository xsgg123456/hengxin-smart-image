"""Migration isolation, with optional disposable PostgreSQL databases."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.overseas import db


BACKEND = Path(__file__).resolve().parents[1]


def migration_environment(url, context='overseas'):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('OVERSEAS_')}
    env['HX_BUSINESS_CONTEXT'] = context
    values = {
        'APP_ENV': 'test', 'DATABASE_URL': url,
        'REDIS_URL': 'redis://localhost:6380/0',
        'MINIO_ENDPOINT': 'localhost:9100',
        'MINIO_ACCESS_KEY': 'fake-overseas-access',
        'MINIO_SECRET_KEY': 'fake-overseas-secret',
        'MINIO_BUCKET': 'overseas-test',
        'CODEX_EXECUTION_ROOT': '/tmp/hx-overseas-test/execution',
        'SKILL_INSTALL_ROOT': '/tmp/hx-overseas-test/skills',
        'LOCAL_SKILL_ROOT': '/tmp/hx-overseas-test/local-skills',
    }
    env.update({'OVERSEAS_' + key: value for key, value in values.items()})
    env.update(APP_ENV='test', DATABASE_URL=url, ENABLE_DEV_IDENTITY='false',
               MINIO_ACCESS_KEY='fake-domestic-key', MINIO_SECRET_KEY='fake-domestic-secret')
    return env


def migrate(env, config='alembic.overseas.ini', *extra):
    return subprocess.run(
        [sys.executable, '-m', 'alembic', '-c', config, 'upgrade', 'head', *extra],
        cwd=BACKEND, env=env, text=True, capture_output=True, timeout=90,
    )


def test_metadata_is_independent_and_does_not_import_domestic_models():
    result = subprocess.run(
        [sys.executable, '-c',
         'import sys; from app.overseas.db import Base; '
         'from app.overseas.auth import models; '
         'from app.overseas.members import models as audits; '
         'from app.overseas.tasks import models as tasks; '
         'from app.overseas.materials import models as materials; '
         'assert set(Base.metadata.tables)=={"overseas_members","overseas_member_roles","overseas_sessions","overseas_member_audits","overseas_tasks","overseas_task_skus","overseas_task_events","overseas_task_requests","overseas_task_outbox","overseas_materials","overseas_material_versions","overseas_requirements_reviews","overseas_task_deletions","overseas_execution_objects"}; '
         'assert "app.models" not in sys.modules; '
         'from app.models import Base as DomesticBase; '
         'assert Base.metadata is not DomesticBase.metadata'],
        cwd=BACKEND, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_existing_pool_is_reused():
    from app.db import session
    assert db.get_engine is session.get_engine
    assert db.session_factory is session.session_factory
    assert db.get_session is session.get_session


def test_revision_tree_has_only_overseas_revisions():
    script = ScriptDirectory.from_config(Config(str(BACKEND / 'alembic.overseas.ini')))
    assert script.get_heads() == [db.SCHEMA_REVISION]
    assert script.get_base() == 'overseas_0001'
    assert len(list(script.walk_revisions())) == 20


@pytest.mark.parametrize('context', ['domestic', 'invalid', ''])
def test_overseas_migrations_reject_wrong_context_before_connecting(context):
    env = migration_environment('postgresql+psycopg://fake:fake@localhost:1/fake_test', context)
    result = migrate(env)
    assert result.returncode != 0
    assert 'HX_BUSINESS_CONTEXT' in result.stderr
    assert 'OperationalError' not in result.stderr


def test_domestic_migration_rejects_overseas_context_before_connecting():
    result = migrate(migration_environment(
        'postgresql+psycopg://fake:fake@localhost:1/fake_test'), 'alembic.ini')
    assert result.returncode != 0
    assert 'Domestic migrations require' in result.stderr
    assert 'OperationalError' not in result.stderr


def test_missing_overseas_configuration_cannot_fall_back_to_domestic():
    env = migration_environment('postgresql+psycopg://fake:fake@localhost:1/fake_test')
    del env['OVERSEAS_DATABASE_URL']
    result = migrate(env, 'alembic.overseas.ini', '--sql')
    assert result.returncode != 0
    assert 'Invalid OVERSEAS_' in result.stderr
    assert 'fake:fake' not in result.stderr


def test_offline_sql_contains_only_overseas_version_table():
    result = migrate(migration_environment(
        'postgresql+psycopg://fake:fake@localhost:1/fake_test'),
        'alembic.overseas.ini', '--sql')
    assert result.returncode == 0, result.stderr
    assert 'CREATE TABLE overseas_alembic_version' in result.stdout
    assert 'CREATE TABLE alembic_version' not in result.stdout
    assert 'CREATE TABLE overseas_members' in result.stdout


@pytest.fixture
def disposable_databases():
    raw_url = os.environ.get('TEST_OVERSEAS_DATABASE_URL')
    if not raw_url:
        pytest.skip('TEST_OVERSEAS_DATABASE_URL is required for isolated PostgreSQL tests')
    url = make_url(raw_url)
    if url.drivername != 'postgresql+psycopg' or not (url.database or '').endswith('_test'):
        pytest.fail('TEST_OVERSEAS_DATABASE_URL must point to a PostgreSQL *_test database')
    admin = create_engine(url, isolation_level='AUTOCOMMIT')
    names = [f'hx_{kind}_{uuid4().hex}_test' for kind in ('overseas', 'domestic')]
    created = []
    try:
        with admin.connect() as connection:
            for name in names:
                connection.execute(text(f'CREATE DATABASE "{name}"'))
                created.append(name)
        yield [url.set(database=name).render_as_string(hide_password=False) for name in names]
    finally:
        with admin.connect() as connection:
            for name in created:
                connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def snapshot(url):
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            tables = sorted(inspect(connection).get_table_names())
            rows = {name: [tuple(row) for row in connection.execute(text(f'SELECT * FROM "{name}"'))]
                    for name in tables}
            return tables, rows
    finally:
        engine.dispose()


@pytest.mark.integration
def test_real_upgrades_are_repeatable_and_domestic_database_is_unchanged(disposable_databases):
    overseas_url, domestic_url = disposable_databases
    domestic_env = migration_environment(domestic_url, 'domestic')
    domestic = migrate(domestic_env, 'alembic.ini')
    assert domestic.returncode == 0, domestic.stderr
    before = snapshot(domestic_url)
    assert 'alembic_version' in before[0]
    assert len(before[0]) > 1
    env = migration_environment(overseas_url)
    for _ in range(2):
        result = migrate(env)
        assert result.returncode == 0, result.stderr
        assert set(snapshot(overseas_url)[0]) == {
            db.VERSION_TABLE, 'overseas_members', 'overseas_member_roles', 'overseas_sessions',
            'overseas_member_audits', 'overseas_tasks', 'overseas_task_skus',
            'overseas_task_events', 'overseas_task_requests', 'overseas_task_outbox',
            'overseas_materials', 'overseas_material_versions', 'overseas_requirements_reviews',
            'overseas_execution_gate', 'overseas_jobs', 'overseas_job_outbox', 'overseas_execution_events', 'overseas_plans', 'overseas_pictures', 'overseas_picture_versions', 'overseas_archives',
            'overseas_skills', 'overseas_skill_versions', 'overseas_settings', 'overseas_management_audit',
            'overseas_installed_skill_availability',
            'overseas_studio_conversations', 'overseas_studio_turns', 'overseas_studio_uploads', 'overseas_studio_pictures',
            'overseas_studio_transcript', 'overseas_studio_material_visibility',
            'overseas_task_deletions', 'overseas_execution_objects', 'overseas_archive_assets', 'overseas_archive_events', 'overseas_archive_deletions',
            'overseas_membership_applications', 'overseas_membership_application_events',
        }
        assert snapshot(overseas_url)[1][db.VERSION_TABLE] == [(db.SCHEMA_REVISION,)]
    assert snapshot(domestic_url) == before
    refused = migrate(migration_environment(domestic_url))
    assert refused.returncode != 0
    assert 'Domestic migration marker found' in refused.stderr
    assert snapshot(domestic_url) == before
    refused = migrate(migration_environment(overseas_url, 'domestic'), 'alembic.ini')
    assert refused.returncode != 0
    assert 'Overseas migration marker found' in refused.stderr
    assert snapshot(overseas_url)[1][db.VERSION_TABLE] == [(db.SCHEMA_REVISION,)]


@pytest.mark.integration
@pytest.mark.parametrize('extra_schema', [False, True])
def test_unrecognized_database_is_rejected_without_writes(disposable_databases, extra_schema):
    overseas_url, _ = disposable_databases
    engine = create_engine(overseas_url)
    try:
        with engine.begin() as connection:
            if extra_schema:
                connection.execute(text('CREATE SCHEMA unrelated'))
                connection.execute(text('CREATE TABLE unrelated.private_data (id integer)'))
            else:
                connection.execute(text('CREATE TABLE unrelated (id integer PRIMARY KEY)'))
                connection.execute(text('INSERT INTO unrelated VALUES (7)'))
        before = snapshot(overseas_url)
        result = migrate(migration_environment(overseas_url))
        assert result.returncode != 0
        assert 'Unrecognized database' in result.stderr
        assert snapshot(overseas_url) == before
        if extra_schema:
            with engine.connect() as connection:
                assert inspect(connection).get_table_names(schema='unrelated') == ['private_data']
    finally:
        engine.dispose()
