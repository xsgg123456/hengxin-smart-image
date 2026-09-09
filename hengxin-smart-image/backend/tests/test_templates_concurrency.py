"""Actual PostgreSQL CAS contention; unique schema, never touch application tables."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.contracts.business import TemplateInput
from app.models import Base
from app.modules.templates.models import TemplateVersionRecord
from app.modules.templates.service import save_template
from app.resource_models import FileRecord, UserRecord


def test_postgres_simultaneous_edit_has_one_winner():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL is required for PostgreSQL concurrency')
    assert url.startswith('postgresql'), 'Only explicit PostgreSQL test configuration is accepted'
    schema = 'test_templates_' + uuid4().hex
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(isolated)
        factory = sessionmaker(isolated, expire_on_commit=False)
        with factory.begin() as session:
            user = UserRecord(id=uuid4(), name='并发测试', role='operator', status='active', identity_source='development')
            session.add(user)
            session.flush()
            file = FileRecord(id=uuid4(), owner_id=user.id, name='a.png', bucket='test',
                              object_key=str(uuid4()), content_type='image/png', checksum='a' * 64,
                              size_bytes=1, width=1, height=1, status='ready')
            session.add(file)
        body = dict(name='并发模板', mode='wallpaper', images=[dict(name='x', url='x', fileId=str(file.id))],
                    skillVersionId=None, active=True, notes='')
        with factory() as session:
            template = save_template(session, user, TemplateInput(**body))
        barrier = Barrier(2)

        def edit(name):
            with factory() as session:
                barrier.wait(timeout=10)
                try:
                    result = save_template(session, user, TemplateInput(**{**body, 'name': name,
                                           'expectedVersion': 1}), UUID(template.id))
                    return result.version
                except HTTPException as error:
                    return error.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(edit, ['甲', '乙'])) == [2, 409]
        with factory() as session:
            versions = session.scalars(select(TemplateVersionRecord)).all()
            assert len(versions) == 2
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()
