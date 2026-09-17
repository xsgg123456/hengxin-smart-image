import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


@pytest.mark.integration
def test_0012_preserves_zip_and_supports_nullable_local_objects():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated PostgreSQL TEST_DATABASE_URL')
    engine = create_engine(url)
    schema = 'test_local_migration_' + uuid4().hex
    spec = importlib.util.spec_from_file_location('local_migration',
        Path(__file__).parents[1] / 'migrations/versions/0012_local_skills.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
            connection.execute(text(f'SET LOCAL search_path TO {schema}'))
            connection.execute(text('CREATE TABLE skill_versions (id integer primary key, '
                'checksum varchar(64) not null, bucket varchar(63) not null, '
                'object_key varchar(200) not null unique)'))
            connection.execute(text("INSERT INTO skill_versions VALUES (1, 'old-hash', 'bucket', 'old.zip')"))
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                module.upgrade()
                assert connection.execute(text('SELECT source_type, checksum, bucket, object_key '
                    'FROM skill_versions WHERE id=1')).one() == ('zip', 'old-hash', 'bucket', 'old.zip')
                assert connection.execute(text('SELECT description FROM skill_versions WHERE id=1')).scalar() is None
                connection.execute(text("INSERT INTO skill_versions "
                    "(id,checksum,bucket,object_key,source_type,description) "
                    "VALUES (2, '', NULL, NULL, 'local', 'version-specific description')"))
                assert connection.execute(text('SELECT description FROM skill_versions WHERE id=2')).scalar() == 'version-specific description'
                with pytest.raises(RuntimeError, match='local registrations'):
                    module.downgrade()
                connection.execute(text('DELETE FROM skill_versions WHERE id=2'))
                module.downgrade()
                columns = {item['name']: item for item in inspect(connection).get_columns('skill_versions')}
                assert 'source_type' not in columns and not columns['bucket']['nullable']
                assert 'description' not in columns
                assert not columns['object_key']['nullable']
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        engine.dispose()
