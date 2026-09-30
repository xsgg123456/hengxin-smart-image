import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


@pytest.mark.parametrize('dialect', ['sqlite', 'postgresql'])
def test_text_kind_migration_keeps_legacy_and_operation_evidence(dialect):
    url = 'sqlite://' if dialect == 'sqlite' else os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated PostgreSQL TEST_DATABASE_URL')
    engine = create_engine(url)
    schema = 'text_kind_' + uuid4().hex
    spec = importlib.util.spec_from_file_location('text_kind_migration',
        Path(__file__).parents[1] / 'migrations/versions/0022_api_text_operation_kind.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        with engine.begin() as connection:
            if dialect == 'postgresql':
                connection.execute(text(f'CREATE SCHEMA {schema}'))
                connection.execute(text(f'SET LOCAL search_path TO {schema}'))
            connection.execute(text('CREATE TABLE api_image_versions (id integer PRIMARY KEY, base_version integer)'))
            connection.execute(text('INSERT INTO api_image_versions VALUES (1,NULL),(2,1)'))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
                assert connection.execute(text('SELECT kind FROM api_image_versions ORDER BY id')).all() == [(None,), (None,)]
                connection.execute(text("INSERT INTO api_image_versions VALUES (3,2,'text_repair')"))
                migration.downgrade()
                migration.upgrade()
                assert connection.execute(text('SELECT kind FROM api_image_versions WHERE id=3')).scalar() == 'text_repair'
    finally:
        if dialect == 'postgresql':
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        engine.dispose()
