from datetime import timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from files_helpers import files_env
from test_skills_packages import archive
from app.core.config import get_settings
from app.models import Job, Outbox, utcnow
from app.modules.skills.models import SkillVersionRecord
from app.resource_models import UserRecord
from app.worker.leases import claim, renew
from app.worker.skill_install import run_install
from app.worker.outbox import dispatch_once


@pytest.fixture
def skills_env(files_env, monkeypatch, tmp_path):
    client, factory, store, identity = files_env
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
    monkeypatch.setenv('SKILL_INSTALL_ROOT', str(tmp_path / 'skills'))
    monkeypatch.setattr(store, 'open', lambda record: BytesIO(store.objects[record.object_key]))
    get_settings.cache_clear()
    yield files_env
    get_settings.cache_clear()


def upload(client, version='1.0.0', data=None):
    return client.post('/api/v1/management/skills', data={'mode': 'text', 'version': version},
                       files={'file': ('demo.zip', data or archive(), 'application/zip')})


def test_upload_install_defaults_status_and_duplicates(skills_env):
    client, factory, store, _ = skills_env
    response = upload(client)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row['status'] == 'uploaded' and row['name'] == 'demo'
    assert upload(client).status_code == 409
    assert client.get('/api/v1/skills').json() == []
    route = f"/api/v1/management/skills/{row['id']}"
    assert client.post(route + '/install').json()['status'] == 'installing'
    assert client.post(route + '/install').status_code == 200
    with factory() as session:
        job = session.scalar(select(Job))
        job_id = str(job.id)
    run_install(job_id, factory, store)
    run_install(job_id, factory, store)
    available = client.get('/api/v1/skills?mode=text').json()
    assert len(available) == 1 and available[0]['status'] == 'available'
    assert client.put('/api/v1/management/skills/defaults', json={
        'wallpaper': None, 'product': None, 'text': row['id']}).status_code == 200
    assert client.put('/api/v1/management/skills/defaults', json={
        'wallpaper': row['id'], 'product': None, 'text': None}).status_code == 422
    assert client.put(route + '/status', json={'status': 'disabled'}).status_code == 200
    assert client.get('/api/v1/skills').json() == []
    with factory() as session:
        record = session.get(SkillVersionRecord, UUID(row['id']))
        assert (Path(record.installed_path) / 'SKILL.md').is_file()
        assert session.get(Job, UUID(job_id)).execution_count == 1
        assert session.get(Outbox, UUID(job_id)).completed_at


@pytest.mark.parametrize('role', ['operator', 'designer', 'design_manager'])
def test_admin_permission(skills_env, role):
    client, factory, _, identity = skills_env
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = role
    assert upload(client).status_code == 403
    assert client.get('/api/v1/management/skills').status_code == 403
    assert client.post(f'/api/v1/management/skills/{uuid4()}/install').status_code == 403
    assert client.put(f'/api/v1/management/skills/{uuid4()}/status', json={'status': 'disabled'}).status_code == 403
    assert client.get('/api/v1/skills').status_code == 200


def test_failed_dependency_keeps_old_version(skills_env):
    client, factory, store, _ = skills_env
    old = upload(client).json()
    client.post(f"/api/v1/management/skills/{old['id']}/install")
    with factory() as session:
        old_job = str(session.scalar(select(Job)).id)
    run_install(old_job, factory, store)
    bad = archive({'SKILL.md': '---\nname: demo\ndescription: test\n---\n',
        'hengxin-skill.json': '{"requires":{"executables":["missing-hengxin-executable-987"]}}'})
    new = upload(client, '2.0.0', bad).json()
    client.post(f"/api/v1/management/skills/{new['id']}/install")
    with factory() as session:
        new_job = str(session.get(SkillVersionRecord, UUID(new['id'])).current_job_id)
    run_install(new_job, factory, store)
    run_install(new_job, factory, store)
    rows = {r['id']: r for r in client.get('/api/v1/management/skills').json()}
    assert rows[old['id']]['status'] == 'available'
    assert rows[new['id']]['status'] == 'failed'
    assert '缺少' in rows[new['id']]['error']


def test_lease_fencing_and_cancelled_job(skills_env):
    client, factory, store, _ = skills_env
    row = upload(client).json()
    client.post(f"/api/v1/management/skills/{row['id']}/install")
    with factory() as session:
        job_id = str(session.scalar(select(Job)).id)
    token = claim(factory, job_id)
    assert token and claim(factory, job_id) is None
    assert renew(factory, job_id, token)
    sent = []
    assert dispatch_once(factory, sent.append) == 0
    with factory.begin() as session:
        session.get(Job, UUID(job_id)).lease_until = utcnow() - timedelta(seconds=1)
    newer = claim(factory, job_id)
    assert newer != token and not renew(factory, job_id, token)
    with factory.begin() as session:
        session.get(Job, UUID(job_id)).status = 'cancelled'
    run_install(job_id, factory, store)
    with factory() as session:
        assert session.get(Job, UUID(job_id)).execution_count == 0
    assert dispatch_once(factory, sent.append) == 0


def test_stale_owner_cannot_publish_and_new_owner_recovers(skills_env, monkeypatch):
    import app.worker.skill_install as installer
    client, factory, store, _ = skills_env
    row = upload(client).json()
    client.post(f"/api/v1/management/skills/{row['id']}/install")
    with factory() as session:
        job_id = str(session.scalar(select(Job)).id)
    original = installer.prepare
    paths = []
    def stolen(record, token, store):
        path = original(record, token, store)
        paths.append(path)
        with factory.begin() as session:
            job = session.get(Job, UUID(job_id))
            job.claim_token = uuid4()
            job.lease_until = utcnow() - timedelta(seconds=1)
        return path
    with monkeypatch.context() as patch:
        patch.setattr(installer, 'prepare', stolen)
        run_install(job_id, factory, store)
    assert not paths[0].exists()
    with factory() as session:
        assert session.get(SkillVersionRecord, UUID(row['id'])).status == 'installing'
    run_install(job_id, factory, store)
    with factory() as session:
        assert session.get(SkillVersionRecord, UUID(row['id'])).status == 'available'


def test_redis_failure_and_permanent_failure_outbox(skills_env):
    client, factory, store, _ = skills_env
    row = upload(client).json()
    client.post(f"/api/v1/management/skills/{row['id']}/install")
    def unavailable(_):
        raise ConnectionError('unavailable')
    with pytest.raises(ConnectionError):
        dispatch_once(factory, unavailable)
    with factory() as session:
        job_id = str(session.scalar(select(Job)).id)
        assert session.get(Outbox, UUID(job_id)).dispatch_count == 0
    sent = []
    assert dispatch_once(factory, sent.append) == 1
    store.objects.clear()
    run_install(job_id, factory, store)
    assert dispatch_once(factory, sent.append) == 0
    with factory() as session:
        assert session.get(Job, UUID(job_id)).status == 'failed'
