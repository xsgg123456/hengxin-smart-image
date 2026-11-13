"""Permission changes fence real management writes in both PostgreSQL orders."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_session
from app.main import app
from app.modules.auth.dependencies import get_identity_id
from app.modules.auth.member_policy import lock_permissions
from app.modules.domestic_studio import management_router
from app.modules.domestic_studio.bindings import lock_admission, read_bindings
from app.modules.domestic_studio.management_router import get_catalog
from app.modules.domestic_studio.policy import WORKSPACES
from app.modules.domestic_studio.skill_state import DomesticSkillState
from app.resource_models import UserRecord
from test_domestic_studio_bindings_pg import database


@pytest.fixture
def context(database):
    UserRecord.__table__.create(database)
    DomesticSkillState.__table__.create(database)
    actor_id, skill_id = uuid4(), str(uuid4())
    factory = sessionmaker(database, expire_on_commit=False)
    with factory.begin() as session:
        session.add(UserRecord(id=actor_id, name='管理员', role='super_admin', status='active',
                               identity_source='development'))
        session.add(DomesticSkillState(name='test-skill', enabled=True, version=1))
    ready = Event()
    class Catalog:
        def list(self):
            return [{'id': skill_id, 'name': 'test-skill', 'displayName': '测试', 'description': ''}]
        def freeze(self, identity):
            assert identity == skill_id
            return {'id': skill_id, 'name': 'test-skill'}
    def db():
        with factory() as session:
            yield session
    def catalog():
        ready.set()
        return Catalog()
    app.dependency_overrides[get_session] = db
    app.dependency_overrides[get_identity_id] = lambda: actor_id
    app.dependency_overrides[get_catalog] = catalog
    client = TestClient(app)
    yield client, factory, actor_id, skill_id, ready
    client.close()
    for dependency in (get_session, get_identity_id, get_catalog):
        app.dependency_overrides.pop(dependency, None)


def send(client, skill_id, operation):
    root = '/api/v1/management/domestic-studio'
    headers = {'X-HX-Request': '1'}
    if operation == 'binding':
        old = dict.fromkeys(WORKSPACES)
        return client.put(root + '/bindings', json={'bindings': old | {'camera': skill_id}, 'expected': old}, headers=headers)
    return client.patch(root + f'/skills/{skill_id}/availability', json={'enabled': False, 'version': 1}, headers=headers)


def assert_value(session, skill_id, operation, written):
    if operation == 'binding':
        assert read_bindings(session)['camera'] == (skill_id if written else None)
    else:
        assert session.get(DomesticSkillState, 'test-skill').enabled is (not written)


@pytest.mark.parametrize('operation', ['binding', 'availability'])
def test_revocation_committed_first_prevents_write(context, operation):
    client, factory, actor_id, skill_id, ready = context
    with factory() as revoker, ThreadPoolExecutor(max_workers=1) as pool:
        lock_permissions(revoker)
        revoker.get(UserRecord, actor_id).role = 'designer'
        revoker.flush()
        future = pool.submit(send, client, skill_id, operation)
        assert ready.wait(5), 'request did not complete initial authentication'
        revoker.commit()
        assert future.result(timeout=10).status_code == 403
    with factory() as session:
        assert_value(session, skill_id, operation, False)


@pytest.mark.parametrize('operation', ['binding', 'availability'])
def test_write_holding_permission_lock_finishes_before_revocation(context, operation, monkeypatch):
    client, factory, actor_id, skill_id, _ = context
    acquired = Event()
    authorize = management_router.authorize_write
    def observed(session, identity):
        actor = authorize(session, identity)
        acquired.set()
        return actor
    monkeypatch.setattr(management_router, 'authorize_write', observed)
    with factory() as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        lock_admission(blocker)
        future = pool.submit(send, client, skill_id, operation)
        assert acquired.wait(5), 'write did not acquire permission lock'
        with factory() as revoker:
            revoker.execute(text("SET LOCAL lock_timeout = '250ms'"))
            with pytest.raises(OperationalError) as error:
                lock_permissions(revoker)
            assert error.value.orig.sqlstate == '55P03'
        blocker.commit()
        assert future.result(timeout=10).status_code == 200
    with factory.begin() as revoker:
        lock_permissions(revoker)
        revoker.get(UserRecord, actor_id).role = 'designer'
    with factory() as session:
        assert session.get(UserRecord, actor_id).role == 'designer'
        assert_value(session, skill_id, operation, True)
