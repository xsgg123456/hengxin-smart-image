"""Migration and mutation races use disposable PostgreSQL schemas only."""
import importlib.util
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text

from app.modules.api_image_edits.models import ApiItem, ApiTask, ApiVersion
from app.modules.api_image_edits.schemas import ReviseItem
from app.modules.api_image_edits.service import submit
from app.modules.api_image_edits.versions import publish_result, revise
from test_api_image_domain import enabled_api
from test_api_image_execution_pg import pg_api

pytestmark = pytest.mark.integration


def migration(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'migrations/versions' / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_0016_migrates_existing_result_and_live_lease():
    url = os.environ.get('API_IMAGE_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated API_IMAGE_TEST_DATABASE_URL')
    engine = create_engine(url)
    schema = 'test_api_migration_' + uuid4().hex
    user, file, task, item, token = [uuid4() for _ in range(5)]
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    try:
        with engine.begin() as connection:
            connection.execute(text(f'SET LOCAL search_path TO {schema}'))
            connection.execute(text('CREATE TABLE users (id uuid primary key)'))
            connection.execute(text('INSERT INTO users VALUES (:id)'), {'id': user})
            with Operations.context(MigrationContext.configure(connection)):
                migration('0015_api_image_edits.py').upgrade()
                connection.execute(text("INSERT INTO api_image_files (id,owner_id,name,bucket,object_key,"
                    "content_type,checksum,size_bytes,width,height,status,created_at,updated_at) VALUES "
                    "(:f,:u,'x','b','k','image/png','hash',1,1,1,'ready',now(),now())"), {'f': file, 'u': user})
                connection.execute(text("INSERT INTO api_image_tasks (id,owner_id,operator_id,name,prompt,"
                    "material_id,parameters,state,events,created_at,updated_at) VALUES "
                    "(:t,:u,:u,'task','prompt',:f,'{}','running','[]',now(),now())"), {'t': task, 'u': user, 'f': file})
                connection.execute(text("INSERT INTO api_image_items (id,task_id,source_id,result_id,position,"
                    "state,created_at,updated_at) VALUES (:i,:t,:f,:f,1,'running',now(),now())"),
                    {'i': item, 't': task, 'f': file})
                connection.execute(text("UPDATE api_image_channel SET item_id=:i,token=:token,"
                    "lease_until=now()+interval '1 hour'"), {'i': item, 'token': token})
                migration('0016_api_image_versions.py').upgrade()
                migration('0016_api_image_versions.py').upgrade()
                row = connection.execute(text('SELECT state,current_version,lease_token,lease_until '
                                              'FROM api_image_items')).one()
                assert row[:3] == ('running', 1, token) and row.lease_until is not None
                assert connection.execute(text('SELECT number,file_id,operator_id FROM api_image_versions')).all() == [(1, file, user)]
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()


def test_concurrent_revision_cas_and_idempotency(pg_api):
    factory, user, data, _ = pg_api
    with factory() as session:
        task_id = submit(session, user, data, 'create')
    with factory.begin() as session:
        task = session.get(ApiTask, task_id)
        item = session.scalar(select(ApiItem))
        publish_result(session, item, task, item.source_id)
        task.state = item.state = 'succeeded'
        item_id = item.id
    barrier = Barrier(4)
    def invoke(index):
        barrier.wait()
        with factory() as session:
            try:
                return revise(session, user, task_id, item_id, ReviseItem(baseVersion=1, text='edit'),
                              'edit-' + str(index))
            except HTTPException as error:
                return error.status_code
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(invoke, range(4)))
    assert results.count(task_id) == 1 and results.count(409) == 3
    winner = results.index(task_id)
    with factory() as session:
        assert revise(session, user, task_id, item_id, ReviseItem(baseVersion=1, text='edit'),
                      'edit-' + str(winner)) == task_id
        assert len(session.scalars(select(ApiVersion)).all()) == 1
