import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.models import Base, Job, Outbox
from app.modules.skills.local_service import check, remove
from app.modules.skills.models import SkillRecord, SkillVersionRecord
from app.resource_models import UserRecord


@pytest.mark.integration
def test_concurrent_checks_enqueue_one_job_and_block_unregister():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated PostgreSQL TEST_DATABASE_URL')
    engine = create_engine(url)
    schema = 'test_local_concurrency_' + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(isolated)
        factory = sessionmaker(isolated, expire_on_commit=False)
        with factory.begin() as session:
            user = UserRecord(id=uuid4(), name='test', role='super_admin', status='active', identity_source='development')
            skill = SkillRecord(name='demo', mode='text', description='')
            session.add_all([user, skill])
            session.flush()
            version = SkillVersionRecord(skill=skill, version='1.0.0', source_type='local',
                status='pending', checksum='')
            session.add(version)
        barrier = Barrier(2)
        def invoke():
            with factory() as session:
                barrier.wait(timeout=5)
                return check(session, user, version.id).current_job_id
        with ThreadPoolExecutor(2) as executor:
            jobs = list(executor.map(lambda _: invoke(), range(2)))
        assert jobs[0] == jobs[1]
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Job)) == 1
            assert session.scalar(select(func.count()).select_from(Outbox)) == 1
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as error:
                remove(session, user, version.id)
            assert error.value.status_code == 409
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()
