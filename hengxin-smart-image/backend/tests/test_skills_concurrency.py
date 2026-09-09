"""Lock reads must refresh versions loaded before another transaction commits."""
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.contracts.management import DefaultSkillIds
from app.modules.skills.models import ModuleSkillBinding, SkillRecord, SkillVersionRecord
from app.modules.skills.router import save_defaults
from app.modules.skills.service import get_version
from app.resource_models import UserRecord


@pytest.mark.parametrize('database', ['sqlite', 'postgres'])
def test_defaults_recheck_status_after_lock(tmp_path, monkeypatch, database):
    schema = None
    if database == 'postgres':
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL required for PostgreSQL race regression')
        assert url.startswith('postgresql')
        engine = create_engine(url)
        schema = 'test_skill_race_' + uuid4().hex
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
        isolated = engine.execution_options(schema_translate_map={None: schema})
    else:
        engine = create_engine('sqlite:///' + str(tmp_path / 'race.db'))
        isolated = engine
    try:
        Base.metadata.create_all(isolated)
        factory = sessionmaker(isolated, expire_on_commit=False)
        with factory.begin() as session:
            user = UserRecord(id=uuid4(), name='test', role='super_admin', status='active', identity_source='development')
            skill = SkillRecord(id=uuid4(), name='test', mode='text', description='test')
            session.add_all([user, skill])
            session.flush()
            record = SkillVersionRecord(id=uuid4(), skill_id=skill.id, version='1', status='available',
                checksum='a' * 64, bucket='test', object_key='test.zip', content_type='application/zip', installed_path='/test')
            session.add(record)
        if database == 'sqlite':
            with factory() as session:
                cached = get_version(session, record.id)
                assert cached.status == 'available'
                with factory.begin() as other:
                    other.get(SkillVersionRecord, record.id).status = 'disabled'
                assert get_version(session, record.id, lock=True).status == 'disabled'
            return
        import app.modules.skills.router as router
        original = router.get_version

        def disable_before_lock(session, version_id, lock=False):
            with factory.begin() as other:
                other.get(SkillVersionRecord, version_id).status = 'disabled'
            refreshed = original(session, version_id, lock)
            assert refreshed.status == 'disabled'
            return refreshed

        monkeypatch.setattr(router, 'get_version', disable_before_lock)
        with factory() as session:
            with pytest.raises(HTTPException) as error:
                save_defaults(DefaultSkillIds(wallpaper=None, product=None, text=str(record.id)), user, session)
            assert error.value.status_code == 422
            session.rollback()
        with factory() as session:
            assert get_version(session, record.id).status == 'disabled'
            assert not session.query(ModuleSkillBinding).filter(ModuleSkillBinding.skill_version_id == record.id).count()
    finally:
        if schema:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()
