import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.models import Base, Job, Outbox
from app.modules.management.models import SystemSettings  # Register tables for standalone execution.
from app.modules.skills.catalog_service import queue_sync
from app.resource_models import UserRecord


@pytest.fixture
def database():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated PostgreSQL TEST_DATABASE_URL')
    engine = create_engine(url)
    schema = 'test_catalog_' + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    try:
        yield engine, schema
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()


@pytest.mark.integration
def test_sync_request_concurrency_coalesces_durable_job(database):
    engine, schema = database
    isolated = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(isolated)
    factory = sessionmaker(isolated, expire_on_commit=False)
    with factory.begin() as session:
        user = UserRecord(id=uuid4(), name='test', role='super_admin', status='active', identity_source='development')
        session.add(user)
    barrier = Barrier(4)
    def invoke(_):
        with factory() as session:
            barrier.wait(timeout=10)
            return queue_sync(session, user)['jobId']
    with ThreadPoolExecutor(4) as executor:
        jobs = list(executor.map(invoke, range(4)))
    assert len(set(jobs)) == 1
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 1
        assert session.scalar(select(func.count()).select_from(Outbox)) == 1


@pytest.mark.integration
def test_0014_idempotent_migration_preserves_legacy_binding_and_payload(database):
    engine, schema = database
    specification = importlib.util.spec_from_file_location('catalog_migration',
        Path(__file__).parents[1] / 'migrations/versions/0014_skill_catalog.py')
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    with engine.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path TO {schema}'))
        connection.execute(text('CREATE TABLE skills (id integer primary key, name text, mode text, description text)'))
        connection.execute(text('CREATE TABLE skill_versions (id integer primary key, skill_id integer, source_type text, checksum text)'))
        connection.execute(text("INSERT INTO skills VALUES (1,'demo','text','old description')"))
        connection.execute(text("INSERT INTO skill_versions VALUES (1,1,'local','original-checksum'), (2,1,'zip','zip-checksum')"))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            module.upgrade()
            assert connection.execute(text('SELECT name,mode,description,catalog_status,removed FROM skills')).one() == (
                'demo', 'text', 'old description', None, False)
            assert connection.execute(text('SELECT source_type,checksum,catalog_snapshot FROM skill_versions ORDER BY id')).all() == [
                ('local', 'original-checksum', False), ('zip', 'zip-checksum', False)]
            module.downgrade()
            assert connection.execute(text('SELECT name,description FROM skills')).one() == ('demo', 'old description')
