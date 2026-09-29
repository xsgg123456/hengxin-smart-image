import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


@pytest.mark.parametrize('dialect', ['sqlite', 'postgresql'])
def test_size_evidence_migration_preserves_history_and_is_idempotent(dialect):
    url = 'sqlite://' if dialect == 'sqlite' else os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated PostgreSQL TEST_DATABASE_URL')
    engine = create_engine(url)
    schema = 'api_dimensions_' + uuid4().hex
    spec = importlib.util.spec_from_file_location('dimension_migration',
        Path(__file__).parents[1] / 'migrations/versions/0021_api_image_dimensions.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        with engine.begin() as connection:
            if dialect == 'postgresql':
                connection.execute(text(f'CREATE SCHEMA {schema}'))
                connection.execute(text(f'SET LOCAL search_path TO {schema}'))
            connection.execute(text('CREATE TABLE api_image_attempts (id integer PRIMARY KEY, state varchar(20))'))
            connection.execute(text("INSERT INTO api_image_attempts VALUES (1, 'succeeded')"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
                assert connection.execute(text('SELECT request_width,request_height,return_width,return_height '
                                                'FROM api_image_attempts WHERE id=1')).one() == (None,) * 4
                columns = inspect(connection).get_columns('api_image_attempts')
                assert all(c['nullable'] for c in columns if c['name'].endswith(('width', 'height')))
                connection.execute(text('INSERT INTO api_image_attempts '
                    '(id,state,request_width,request_height,return_width,return_height) '
                    "VALUES (2,'succeeded',800,1520,1254,1254)"))
                migration.downgrade()
                assert connection.execute(text('SELECT count(*) FROM api_image_attempts')).scalar() == 2
                assert connection.execute(text('SELECT return_width FROM api_image_attempts WHERE id=2')).scalar() == 1254
    finally:
        if dialect == 'postgresql':
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        engine.dispose()
