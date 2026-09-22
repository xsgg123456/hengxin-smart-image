"""Opt-in PostgreSQL concurrency tests; every test owns an isolated temporary schema."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.models import Base, utcnow
from app.modules.api_image_edits.claims import claim, start_attempt
from app.modules.api_image_edits.files import save_upload
from app.modules.api_image_edits.models import ApiChannel, ApiItem, ApiTask
from app.modules.api_image_edits.outcomes import save_response
from app.modules.api_image_edits.relay import RelayResult
from app.modules.api_image_edits.schemas import CreateTask
from app.modules.api_image_edits.service import submit
from app.modules.files.validation import validate_image
from app.resource_models import UserRecord
from files_helpers import MemoryStore, image_bytes
from test_api_image_domain import enabled_api
from io import BytesIO
from types import SimpleNamespace

pytestmark = pytest.mark.integration


@pytest.fixture
def pg_api():
    url = os.environ.get('API_IMAGE_TEST_DATABASE_URL')
    if not url:
        pytest.skip('API_IMAGE_TEST_DATABASE_URL is not set')
    schema = 'test_api_image_' + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    tables = [t for t in Base.metadata.sorted_tables if t.name == 'users' or t.name.startswith('api_image_')]
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(engine, expire_on_commit=False)
    store = MemoryStore()
    with factory() as session:
        user = UserRecord(id=uuid4(), name='隔离测试', role='super_admin', status='active',
                          identity_source='development')
        session.add(user)
        session.commit()
        image = validate_image(SimpleNamespace(file=BytesIO(image_bytes()),
                               filename='x.png', content_type='image/png'))
        file = save_upload(session, store, user, image)
        payload = CreateTask(name='并发测试', prompt='p', originalFileIds=[file.id], materialFileId=file.id)
    try:
        yield factory, user, payload, store
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


def test_postgres_concurrent_submit_and_single_global_claim(pg_api):
    factory, user, data, _ = pg_api
    barrier = Barrier(4)
    def create_same(_):
        barrier.wait()
        with factory() as session:
            return submit(session, user, data, 'same-key')
    with ThreadPoolExecutor(max_workers=4) as pool:
        task_ids = list(pool.map(create_same, range(4)))
    assert len(set(task_ids)) == 1
    with factory() as session:
        assert len(session.scalars(select(ApiTask)).all()) == 1
    barrier = Barrier(4)
    def compete(_):
        barrier.wait()
        return claim(factory)
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(compete, range(4)))
    assert sum(value is not None for value in claims) == 1


def test_postgres_expired_claim_fences_late_results(pg_api):
    factory, user, data, _ = pg_api
    with factory() as session:
        submit(session, user, data, 'one')
        submit(session, user, data, 'two')
    item_id, token, _ = claim(factory)
    assert start_attempt(factory, item_id, token)
    with factory.begin() as session:
        session.get(ApiItem, item_id).lease_until = utcnow() - timedelta(seconds=1)
    assert claim(factory) is None
    assert not save_response(factory, item_id, token, RelayResult(image_bytes=image_bytes()))
    assert claim(factory) is None
    with factory() as session:
        item = session.get(ApiItem, item_id)
        assert item.state == 'uncertain' and item.result_bytes is None
        assert item.lease_token is None
