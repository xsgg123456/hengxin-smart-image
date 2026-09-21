import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


@pytest.mark.integration
def test_0013_preserves_old_rounds_and_enforces_input_foreign_keys():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated PostgreSQL TEST_DATABASE_URL')
    engine = create_engine(url)
    schema = 'test_revision_migration_' + uuid4().hex
    spec = importlib.util.spec_from_file_location('revision_migration',
        Path(__file__).parents[1] / 'migrations/versions/0013_revision_inputs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
            connection.execute(text(f'SET LOCAL search_path TO {schema}'))
            connection.execute(text('CREATE TABLE image_versions (id uuid primary key)'))
            connection.execute(text('CREATE TABLE files (id uuid primary key)'))
            connection.execute(text('CREATE TABLE execution_rounds (id integer primary key, note text)'))
            connection.execute(text("INSERT INTO execution_rounds VALUES (1, 'old')"))
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                module.upgrade()
                assert connection.execute(text('SELECT note, base_version_id, annotation_file_id '
                    'FROM execution_rounds')).one() == ('old', None, None)
                foreign_keys = inspect(connection).get_foreign_keys('execution_rounds')
                assert {f['referred_table'] for f in foreign_keys} == {'files', 'image_versions'}
                module.downgrade()
                assert [c['name'] for c in inspect(connection).get_columns('execution_rounds')] == ['id', 'note']
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        engine.dispose()
