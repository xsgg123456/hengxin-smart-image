"""Actual PostgreSQL admission/cleanup fencing on separate connections."""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import Job
from app.modules.domestic_studio import skill_publication, skill_references
from app.modules.domestic_studio.bindings import read_bindings, save_bindings
from app.modules.domestic_studio.installed_skills import DomesticInstalledSkills
from app.modules.domestic_studio.models import SkillExecutionReference, SkillPublicationAudit
from app.modules.domestic_studio.skill_state import DomesticSkillState
from app.overseas.management.skill_transfer_schema import SkillDelete
from app.overseas.management.skill_transfer_store import TransferStore
from app.resource_models import UserRecord
from test_domestic_installed_skills import install_fixture
from test_domestic_studio_bindings_pg import database


def test_real_postgres_pins_inflight_job_before_catalog_delete(database, tmp_path):
    for table in (UserRecord.__table__, Job.__table__, DomesticSkillState.__table__,
                  SkillExecutionReference.__table__, SkillPublicationAudit.__table__):
        table.create(database)
    root = tmp_path / 'domestic'
    root.mkdir()
    install_fixture(tmp_path, root)
    installed = DomesticInstalledSkills(root, protected=False)
    skill = installed.list()[0]
    original = installed.freeze(skill['id'])
    store = TransferStore(tmp_path / 'transfers', root)
    actor_id, job_id = uuid4(), uuid4()
    with Session(database) as session:
        session.add(UserRecord(id=actor_id, name='管理员', role='super_admin', status='active',
                               identity_source='development'))
        session.add(DomesticSkillState(name=skill['name'], enabled=True, version=1))
        session.flush()
        current = read_bindings(session)
        save_bindings(session, current | {'camera': skill['id']}, lambda _: None, expected=current)
        session.commit()
    body = SkillDelete(release=original['installedRelease'], checksum=original['checksum'], version=1)
    with Session(database) as first, Session(database) as second:
        job = Job(id=job_id, idempotency_key=str(job_id), payload_hash='a' * 64, value='{}',
                  kind=skill_references.JOB_KIND, status='running')
        first.add(job)
        first.flush()
        assert skill_references.freeze_and_pin(first, job, 'camera', installed) == {'skill': original}
        second.execute(text("SET LOCAL lock_timeout = '250ms'"))
        with pytest.raises(OperationalError) as error:
            skill_publication.delete(store, second, actor_id, skill['id'], body)
        assert error.value.orig.sqlstate == '55P03'
        second.rollback()
        first.commit()
        previous = read_bindings(second)
        save_bindings(second, dict.fromkeys(previous), lambda _: None, expected=previous)
        second.commit()
        with pytest.raises(HTTPException) as error:
            skill_publication.delete(store, second, actor_id, skill['id'], body)
        assert error.value.status_code == 409
        second.rollback()
    with Session(database) as session:
        session.get(Job, job_id).status = 'succeeded'
        session.commit()
        result = skill_publication.delete(store, session, actor_id, skill['id'], body)
        assert result['deleted'] is True
        assert installed.frozen_package(original).name == skill['name']
