"""HTTP/state/fencing coverage; Linux filesystem/sandbox tests are separate."""
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from files_helpers import files_env
from test_skills import skills_env
from app.models import Job, Outbox
from app.modules.skills.local_tree import LocalTree
from app.modules.skills.models import SkillVersionRecord, SkillAuditRecord
from app.resource_models import UserRecord
from app.worker.skill_check import run_check

BASE = '/api/v1/management/skills'


def register(client, **changes):
    return client.post(BASE + '/register', json={
        'name': 'local-demo', 'mode': 'text', 'version': '1.0.0', **changes})


def job_for(factory, row):
    with factory() as session:
        return str(session.get(SkillVersionRecord, UUID(row['id'])).current_job_id)


def test_registration_duplicate_pending_permission_and_retired_upload(skills_env):
    client, factory, store, identity = skills_env
    assert client.post(BASE, content=b'not even a zip').status_code == 410
    row = register(client).json()
    assert row['sourceType'] == 'local' and row['status'] == 'pending' and row['checksum'] == ''
    assert store.objects == {}
    assert register(client).status_code == 409
    assert client.put(f"{BASE}/{row['id']}/status", json={'status': 'available'}).status_code == 409
    with factory() as session:
        stored = session.get(SkillVersionRecord, UUID(row['id']))
        assert stored.bucket is None and stored.object_key is None
    for role in ('operator', 'designer', 'design_manager'):
        with factory.begin() as session:
            session.get(UserRecord, identity[0]).role = role
        assert register(client, version='2.0.0').status_code == 403
        assert client.post(f"{BASE}/{row['id']}/check").status_code == 403
        assert client.delete(f"{BASE}/{row['id']}").status_code == 403


@pytest.mark.parametrize('changes', [dict(name='../escape'), dict(name='/abs'), dict(name='x/y'),
    dict(name='x' * 101), dict(version='../1.0.0'), dict(mode='bad'), dict(description='x' * 2001)])
def test_register_validation(skills_env, changes):
    assert register(skills_env[0], **changes).status_code == 422


@pytest.mark.parametrize('version,status', [('01.0.0', 422), ('1.0.0-alpha..1', 422),
    ('1.0.0-01', 422), ('1.0.0+build.1', 201), ('１.0.0', 422),
    ('1.0.0+' + 'a' * 95, 422), ('1.0.0-0.alpha+001', 201)])
def test_register_strict_semver(skills_env, version, status):
    assert register(skills_env[0], version=version).status_code == status


def test_check_freezes_hash_never_auto_enables_and_recheck_cannot_replace_hash(skills_env, monkeypatch):
    import app.worker.skill_check as worker
    client, factory, _, _ = skills_env
    row = register(client).json()
    route = f"{BASE}/{row['id']}"
    assert client.post(route + '/check').json()['status'] == 'checking'
    original_job = job_for(factory, row)
    assert client.post(route + '/check').json()['status'] == 'checking'
    assert job_for(factory, row) == original_job
    assert client.delete(route).status_code == 409
    tree = LocalTree(Path('/published/demo'), 'a' * 64, {}, {})
    monkeypatch.setattr(worker, 'validate_local', lambda record: tree)
    run_check(original_job, factory)
    run_check(original_job, factory)
    result = client.get(BASE).json()[0]
    assert result['status'] == 'verified' and result['checksum'] == tree.checksum
    assert client.get('/api/v1/skills').json() == []
    assert client.put(route + '/status', json={'status': 'available'}).status_code == 200
    assert len(client.get('/api/v1/skills').json()) == 1
    assert client.post(route + '/check').json()['status'] == 'checking'
    assert client.get('/api/v1/skills').json() == []
    run_check(job_for(factory, row), factory)
    assert client.get(BASE).json()[0]['status'] == 'verified'
    client.post(route + '/check')
    monkeypatch.setattr(worker, 'validate_local', lambda record: LocalTree(tree.path, 'b' * 64, {}, {}))
    run_check(job_for(factory, row), factory)
    result = client.get(BASE).json()[0]
    assert result['status'] == 'invalid' and result['checksum'] == 'a' * 64
    assert '内容已变化' in result['error']
    with factory() as session:
        assert session.get(Job, UUID(original_job)).execution_count == 1
        assert session.get(Outbox, UUID(original_job)).completed_at


def test_missing_deployment_failure_retry_stale_claim_and_removal_audit(skills_env, monkeypatch):
    import app.worker.skill_check as worker
    client, factory, _, _ = skills_env
    row = register(client).json()
    route = f"{BASE}/{row['id']}"
    def missing(record):
        raise ValueError('Skill 尚未部署或文件已缺失')
    monkeypatch.setattr(worker, 'validate_local', missing)
    client.post(route + '/check')
    run_check(job_for(factory, row), factory)
    assert client.get(BASE).json()[0]['status'] == 'invalid'
    client.post(route + '/check')
    job_id = job_for(factory, row)
    def steal(record):
        with factory.begin() as session:
            session.get(Job, UUID(job_id)).claim_token = uuid4()
        return LocalTree(Path('/x'), 'c' * 64, {}, {})
    monkeypatch.setattr(worker, 'validate_local', steal)
    run_check(job_id, factory)
    assert client.get(BASE).json()[0]['status'] == 'checking'
    assert client.delete(route).status_code == 409
    # An unrelated unreferenced registration may be removed; no filesystem operation.
    other = register(client, version='2.0.0').json()
    assert client.delete(f"{BASE}/{other['id']}").status_code == 204
    with factory() as session:
        assert 'unregister' in session.scalars(select(SkillAuditRecord.action)).all()


def test_default_reference_blocks_removal(skills_env):
    from app.modules.skills.models import ModuleSkillBinding
    client, factory, _, _ = skills_env
    row = register(client).json()
    with factory.begin() as session:
        session.add(ModuleSkillBinding(mode='text', skill_version_id=UUID(row['id'])))
    assert client.delete(f"{BASE}/{row['id']}").status_code == 409


def test_each_registered_version_keeps_its_own_description(skills_env):
    client, factory, _, _ = skills_env
    first = register(client, description='第一版说明').json()
    second = register(client, version='2.0.0', description='第二版说明').json()
    empty = register(client, version='3.0.0').json()
    expected = {first['id']: '第一版说明', second['id']: '第二版说明', empty['id']: ''}
    assert {row['id']: row['description'] for row in (first, second, empty)} == expected
    assert {row['id']: row['description'] for row in client.get(BASE).json()} == expected
    with factory() as session:
        assert {str(row.id): row.description for row in session.scalars(select(SkillVersionRecord))} == expected


def test_historical_zip_without_version_description_falls_back_to_skill(skills_env):
    from test_skills import upload
    client, factory, _, _ = skills_env
    historical = upload(client).json()
    with factory.begin() as session:
        row = session.get(SkillVersionRecord, UUID(historical['id']))
        row.description = None
        row.skill.description = '历史 ZIP 说明'
    assert client.get(BASE).json()[0]['description'] == '历史 ZIP 说明'
