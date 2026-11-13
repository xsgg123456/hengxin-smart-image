"""Publisher recovery must take membership permission before admission."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.modules.auth.member_policy import lock_permissions
from app.modules.domestic_studio import skill_publication
from app.modules.domestic_studio.bindings import lock_admission
from app.modules.domestic_studio.models import SkillPublicationAudit
from app.overseas.management.skill_publisher import create_app
from app.overseas.management.skill_transfer_store import TransferStore, atomic_json
from app.resource_models import UserRecord
from test_domestic_studio_bindings_pg import database


@pytest.mark.parametrize('operation', ['install', 'delete'])
def test_recovery_does_not_invert_permission_and_admission_locks(database, tmp_path, monkeypatch, operation):
    UserRecord.__table__.create(database)
    SkillPublicationAudit.__table__.create(database)
    factory = sessionmaker(database, expire_on_commit=False)
    actor_id, target_id = uuid4(), uuid4()
    with factory.begin() as session:
        session.add(UserRecord(id=actor_id, name='管理员', role='super_admin', status='active',
                               identity_source='development'))
    root = tmp_path / 'skills'
    stage = root / 'releases' / '.install-abcde123'
    stage.mkdir(parents=True)
    (stage / 'manifest.json').write_bytes(b'{"items": [], "schema": 2}')
    store = TransferStore(tmp_path / 'transfers', root)
    reached_authorization = Event()
    authorize = skill_publication.authorize
    def observed(session, identity):
        reached_authorization.set()
        return authorize(session, identity)
    monkeypatch.setattr(skill_publication, 'authorize', observed)
    publisher = create_app(store, factory, publication=skill_publication, allow_maintenance=False)
    client = TestClient(publisher)
    def request():
        headers = {'X-Actor-Id': str(actor_id)}
        if operation == 'install':
            return client.post(f'/transfers/{target_id}/install', json={'baseRelease': None}, headers=headers)
        return client.request('DELETE', f'/skills/{target_id}', headers=headers,
                              json={'release': 'a' * 64, 'checksum': 'b' * 64, 'version': 1})
    try:
        with factory() as administrator, ThreadPoolExecutor(max_workers=1) as pool:
            lock_permissions(administrator)
            future = pool.submit(request)
            assert reached_authorization.wait(5)
            administrator.execute(text("SET LOCAL lock_timeout = '500ms'"))
            lock_admission(administrator)  # succeeds while publisher waits for permissions
            administrator.commit()
            assert future.result(timeout=10).status_code == 404
        assert (root / 'current.json').is_file()
        assert (stage / 'manifest.json').read_bytes() == b'{"items": [], "schema": 2}'
    finally:
        client.close()


def test_permission_is_rechecked_when_recovery_commits_before_transfer_access(database, tmp_path, monkeypatch):
    UserRecord.__table__.create(database)
    SkillPublicationAudit.__table__.create(database)
    factory = sessionmaker(database, expire_on_commit=False)
    actor_id = uuid4()
    with factory.begin() as session:
        session.add(UserRecord(id=actor_id, name='管理员', role='super_admin', status='active',
                               identity_source='development'))
    root = tmp_path / 'skills'
    root.mkdir()
    store = TransferStore(tmp_path / 'transfers', root)
    release = skill_publication.shared.prepare_release(store, [])
    atomic_json(root / '.pending.json', {'audit': str(uuid4()), 'before': release, 'after': release})
    recovered, revoked = Event(), Event()
    original = skill_publication.recover
    def pause_after_recovery(store, session):
        original(store, session)
        recovered.set()
        assert revoked.wait(5)
    monkeypatch.setattr(skill_publication, 'recover', pause_after_recovery)
    client = TestClient(create_app(store, factory, publication=skill_publication, allow_maintenance=False))
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(client.get, '/transfers', headers={'X-Actor-Id': str(actor_id)})
            assert recovered.wait(5)
            with factory.begin() as session:
                lock_permissions(session)
                session.get(UserRecord, actor_id).role = 'designer'
            revoked.set()
            assert future.result(timeout=10).status_code == 403
    finally:
        revoked.set()
        client.close()
