from uuid import UUID, uuid4
from datetime import timedelta
import pytest
from sqlalchemy import select
from app.core.config import get_settings
from app.models import Job, Outbox, utcnow
from app.modules.tasks.models import ExecutionGate, TaskRecord, RoundRecord, ImageVersion, TaskRequest
from app.modules.tasks.claims import claim, sweep_expired
from app.modules.tasks.results import publish_results
from app.execution.fixture_runner import run_generation
from app.modules.skills.models import SkillVersionRecord
from files_helpers import files_env
from test_templates_skills import add_skill
from test_files import upload


@pytest.fixture
def task_env(files_env, monkeypatch):
    monkeypatch.setattr(get_settings(), 'enable_fixture_executor', True)
    monkeypatch.setattr(get_settings(), 'fixture_delay_seconds', 0)
    client, factory, store, identity = files_env
    with factory.begin() as session:
        session.add(ExecutionGate(id=1))
    yield files_env


def body(env, mode='text'):
    client, factory, _, _ = env
    skill = add_skill(factory, mode=mode)
    source = upload(client).json()
    data = dict(mode=mode, name='测试任务', sku='SKU', sources=[source], note='修改文字', skillVersionId=skill)
    if mode != 'text':
        template = client.post('/api/v1/templates', json=dict(name='模板', mode=mode,
            images=[source, source], skillVersionId=skill, active=True, notes='冻结')).json()
        data.update(templateId=template['id'], templateVersion=template['version'])
    return data


def submit(env, data=None, key='key'):
    return env[0].post('/api/v1/tasks', json=data or body(env), headers={'Idempotency-Key': key})


def job_for(factory, receipt):
    with factory() as session:
        return session.get(RoundRecord, UUID(receipt['roundId'])).job_id


@pytest.mark.parametrize('mode', ['text', 'wallpaper', 'product'])
def test_real_result_roundtrip_frozen_and_idempotent(task_env, mode):
    client, factory, store, _ = task_env
    data = body(task_env, mode)
    response = submit(task_env, data)
    assert response.status_code == 202, response.text
    receipt = response.json()
    assert submit(task_env, data).json() == receipt
    assert submit(task_env, {**data, 'note': '其他'}).status_code == 409
    with factory.begin() as session:
        session.get(SkillVersionRecord, UUID(data['skillVersionId'])).status = 'disabled'
    assert submit(task_env, data).json() == receipt
    job_id = job_for(factory, receipt)
    run_generation(job_id, factory, store)
    run_generation(job_id, factory, store)
    detail = client.get('/api/v1/tasks/' + receipt['taskId']).json()
    assert detail['task']['state'] == '待查看', detail
    assert detail['task']['sessionId'] is None and detail['task']['executionSource'] == 'fixture'
    assert not detail['executionControl']['canRetry']
    assert len(detail['slots']) == (1 if mode == 'text' else 2)
    for image in detail['task']['images']:
        assert client.get(image['url']).status_code == 200
    with factory() as session:
        assert session.get(Job, job_id).execution_count == 1
        assert len(session.scalars(select(TaskRecord)).all()) == 1
        assert len(session.scalars(select(TaskRequest)).all()) == 1


def test_unavailable_and_replay(task_env, monkeypatch):
    data = body(task_env)
    receipt = submit(task_env, data).json()
    monkeypatch.setattr(get_settings(), 'enable_fixture_executor', False)
    assert submit(task_env, data).json() == receipt
    assert submit(task_env, data, 'new').status_code == 503
    assert task_env[0].post('/api/v1/tasks', json=data).status_code == 422


@pytest.mark.parametrize('change', [{'name': ' '}, {'name': 'a'*61}, {'sku': 'a'*81},
    {'note': ''}, {'note': 'a'*1001}, {'sources': []}, {'sources': [{'name': 'x', 'url':'x'}]}])
def test_validation(task_env, change):
    assert submit(task_env, {**body(task_env), **change}).status_code == 422


@pytest.mark.parametrize('stage', ['queued', 'running', 'uploaded'])
def test_cancellation_fences(task_env, stage):
    client, factory, store, _ = task_env
    receipt = submit(task_env).json()
    job_id = job_for(factory, receipt)
    delete = lambda: client.delete('/api/v1/tasks/' + receipt['taskId'])
    if stage == 'queued':
        assert delete().status_code == 200
        run_generation(job_id, factory, store)
    elif stage == 'running':
        token = claim(factory, job_id)
        assert delete().status_code == 200
        assert not publish_results(factory, job_id, token, [])
    else:
        run_generation(job_id, factory, store, after_upload=delete)
    with factory() as session:
        assert session.scalar(select(ImageVersion)) is None
        assert session.get(TaskRecord, UUID(receipt['taskId'])).deleted_at
    assert client.get('/api/v1/tasks').json()['total'] == 0


def test_expired_unknown_blocks_reclaim_and_global_capacity(task_env):
    _, factory, _, _ = task_env
    first = submit(task_env).json()
    second = submit(task_env, key='two').json()
    one, two = job_for(factory, first), job_for(factory, second)
    token = claim(factory, one)
    assert token and claim(factory, two) is None
    with factory.begin() as session:
        session.get(Job, one).lease_until = utcnow() - timedelta(seconds=1)
    sweep_expired(factory)
    assert claim(factory, one) is None and claim(factory, two) is None
    assert not publish_results(factory, one, token, [])
    with factory() as session:
        assert session.get(Job, one).status == 'uncertain'


def test_template_file_unready_and_snapshot_version(task_env):
    from app.resource_models import FileRecord
    data = body(task_env, 'wallpaper')
    assert submit(task_env, {**data, 'templateVersion': 2}).status_code == 409
    with task_env[1].begin() as session:
        session.get(FileRecord, UUID(data['sources'][0]['fileId'])).status = 'failed'
    data['sources'] = [upload(task_env[0]).json()]
    assert submit(task_env, data).status_code == 422


@pytest.mark.parametrize('role', ['super_admin', 'design_manager', 'designer', 'operator'])
def test_cross_owner_shared_listing_delete_and_audit(task_env, role):
    from app.resource_models import UserRecord, DeletionRecord
    client, factory, _, identity = task_env
    receipt = submit(task_env).json()
    with factory.begin() as session:
        user = UserRecord(id=uuid4(), name='其他人', role=role, status='active', identity_source='development')
        session.add(user)
        identity[0] = user.id
    path = '/api/v1/tasks/' + receipt['taskId']
    assert client.get(path).status_code == 200
    assert client.get('/api/v1/tasks?state=processing&pageSize=1').json()['total'] == 1
    assert client.get('/api/v1/tasks?search=不存在').json()['items'] == []
    assert client.delete(path).json()['operatorId'] == str(identity[0])
    with factory() as session:
        assert session.scalar(select(DeletionRecord)).operator_id == identity[0]


def test_old_token_and_missing_active_lease_cannot_publish(task_env):
    _, factory, _, _ = task_env
    receipt = submit(task_env).json()
    job_id = job_for(factory, receipt)
    token = claim(factory, job_id)
    assert not publish_results(factory, job_id, uuid4(), [])
    with factory.begin() as session:
        session.get(Job, job_id).lease_until = None
    assert not publish_results(factory, job_id, token, [])


def test_cross_operator_round_result_ownership(task_env):
    from app.resource_models import UserRecord, FileRecord
    from app.modules.tasks.service import accept_round
    from app.contracts.business import RevisionInput
    client, factory, store, _ = task_env
    receipt = submit(task_env).json()
    run_generation(job_for(factory, receipt), factory, store)
    with factory.begin() as session:
        other = UserRecord(id=uuid4(), name='其他人', role='designer', status='active', identity_source='development')
        session.add(other)
    with factory() as session:
        accepted = accept_round(session, other, UUID(receipt['taskId']), RevisionInput(
            taskId=receipt['taskId'], target=None, note='返工意见'), 'other')
    run_generation(job_for(factory, accepted.model_dump()), factory, store)
    with factory() as session:
        version = session.scalar(select(ImageVersion).where(ImageVersion.round_id == UUID(accepted.roundId)))
        assert session.get(FileRecord, version.file_id).owner_id == other.id
