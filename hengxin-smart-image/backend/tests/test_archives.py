from uuid import UUID, uuid4
import pytest
from sqlalchemy import func, select

from app.resource_models import DeletionRecord, UserRecord
from app.modules.archives.models import ArchiveImage, ArchiveRecord
from app.modules.tasks.models import ResultSlotRecord, RoundRecord
from app.execution.fixture_runner import run_generation
from files_helpers import files_env
from test_tasks import task_env, job_for
from test_revisions import ready, detail, revise, change_state


def archive(env, receipt, key=None, versions=None):
    return env[0].post('/api/v1/tasks/' + receipt['taskId'] + '/archives',
        headers={'Idempotency-Key': key} if key is not None else {},
        json={'imageVersionIds': versions} if versions is not None else None)


def test_snapshot_replay_revision_delete_and_download(task_env):
    client, factory, store, _ = task_env
    receipt = ready(task_env, 'wallpaper')
    before = detail(task_env, receipt)
    versions = [s['currentVersionId'] for s in before['slots']]
    response = archive(task_env, receipt, 'first', versions)
    assert response.status_code == 200, response.text
    saved = response.json()
    bytes_before = [client.get(p['url']).content for p in saved['images']]
    assert archive(task_env, receipt).json() == saved
    assert detail(task_env, receipt)['task']['archived']
    assert client.get('/api/v1/tasks').json()['stats']['archived'] == 1
    accepted = revise(task_env, receipt, target=0).json()
    assert archive(task_env, receipt).status_code == 409
    assert archive(task_env, receipt, 'first', versions).json() == saved
    run_generation(job_for(factory, accepted), factory, store)
    assert archive(task_env, receipt, 'first', versions).json() == saved
    assert archive(task_env, receipt, 'new', versions).status_code == 409
    newer = archive(task_env, receipt).json()
    assert newer['id'] != saved['id']
    assert newer['imageVersionIds'][0] != saved['imageVersionIds'][0]
    assert newer['imageVersionIds'][1] == saved['imageVersionIds'][1]
    assert client.get('/api/v1/archives/' + saved['id']).json() == saved
    assert [client.get(p['url']).content for p in saved['images']] == bytes_before
    assert client.delete('/api/v1/tasks/' + receipt['taskId']).status_code == 200
    assert client.get('/api/v1/archives/' + saved['id']).json() == saved
    assert [client.get(p['url']).content for p in saved['images']] == bytes_before
    assert client.delete('/api/v1/archives/' + saved['id']).status_code == 204
    assert client.get('/api/v1/archives/' + saved['id']).status_code == 404
    assert client.get('/api/v1/archives').json()['total'] == 1
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ArchiveImage)) == 4


@pytest.mark.parametrize('status', ['queued', 'running', 'collecting', 'cancelling', 'uncertain', 'failed', 'partial'])
def test_unfinished_or_failed_round_cannot_archive_old_images(task_env, status):
    receipt = ready(task_env)
    change_state(task_env, receipt, status)
    assert archive(task_env, receipt).status_code == 409


@pytest.mark.parametrize('change', ['missing', 'error'])
def test_incomplete_whole_set_rejected_despite_successful_current_round(task_env, change):
    receipt = ready(task_env, 'wallpaper')
    with task_env[1].begin() as session:
        slot = session.scalar(select(ResultSlotRecord).where(ResultSlotRecord.task_id == UUID(receipt['taskId'])))
        if change == 'missing':
            slot.current_version_id = None
        else:
            slot.error = '此图上轮失败'
    assert archive(task_env, receipt).status_code == 409


@pytest.mark.parametrize('role', ['super_admin', 'design_manager', 'designer', 'operator'])
def test_shared_authorization_and_actual_actor(task_env, role):
    client, factory, _, identity = task_env
    receipt = ready(task_env)
    with factory.begin() as session:
        user = UserRecord(id=uuid4(), name='归档者', role=role, status='active', identity_source='development')
        session.add(user)
        identity[0] = user.id
    saved = archive(task_env, receipt, 'key').json()
    assert saved['ownerId'] == str(identity[0])
    path = '/api/v1/archives/' + saved['id']
    assert client.get(path).status_code == 200
    with factory.begin() as session:
        session.get(UserRecord, user.id).status = 'disabled'
    assert archive(task_env, receipt, 'key').status_code == 403
    assert client.get(path).status_code == 403
    assert client.get(saved['images'][0]['url']).status_code == 403
    with factory.begin() as session:
        session.get(UserRecord, user.id).status = 'active'
        identity[0] = session.get(ArchiveRecord, UUID(saved['id'])).owner_id
    assert client.delete(path).status_code == 204
    assert not detail(task_env, receipt)['task']['archived']
    assert client.get('/api/v1/tasks').json()['stats']['archived'] == 0
    with factory() as session:
        audit = session.scalar(select(DeletionRecord).where(DeletionRecord.resource_type == 'archive'))
        assert audit.operator_id == user.id
    assert client.get(saved['images'][0]['url']).status_code == 200
    assert archive(task_env, receipt, 'key').status_code == 404
    assert archive(task_env, receipt, 'new-key').status_code == 200
    identity[0] = None
    assert client.get('/api/v1/archives').status_code == 401


def test_filters_pagination_validation_and_changed_key(task_env):
    client = task_env[0]
    assert client.get('/api/v1/archives').json()['items'] == []
    receipt = ready(task_env)
    saved = archive(task_env, receipt, 'key').json()
    assert archive(task_env, receipt, 'key', [str(uuid4())]).status_code == 409
    assert archive(task_env, receipt, ' ').status_code == 422
    assert archive(task_env, receipt, versions=[]).status_code == 422
    assert archive(task_env, receipt, versions=['bad']).status_code == 422
    assert client.get('/api/v1/archives?search=测试&pageSize=1').json()['items'][0] == saved
    for query in ['search=不存在', 'search=%25', 'mode=wallpaper', 'page=2&pageSize=1']:
        assert client.get('/api/v1/archives?' + query).json()['items'] == []
    for query in ['page=0', 'pageSize=101', 'mode=bad']:
        assert client.get('/api/v1/archives?' + query).status_code == 422
    assert client.get('/api/v1/archives/bad').status_code == 422


@pytest.mark.parametrize('role', ['super_admin', 'design_manager', 'designer', 'operator'])
def test_each_role_deletes_another_users_archive_and_preserves_task(task_env, role):
    client, factory, _, identity = task_env
    receipt = ready(task_env)
    saved = archive(task_env, receipt).json()
    with factory.begin() as session:
        other = UserRecord(id=uuid4(), name='跨归档删除者', role=role, status='active', identity_source='development')
        session.add(other)
        identity[0] = other.id
    assert str(identity[0]) != saved['ownerId']
    path = '/api/v1/archives/' + saved['id']
    assert client.get(path).status_code == 200
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404
    assert detail(task_env, receipt)['task']['id'] == receipt['taskId']
    assert client.get(saved['images'][0]['url']).status_code == 200
    with factory() as session:
        record = session.scalar(select(DeletionRecord).where(DeletionRecord.resource_type == 'archive'))
        assert record.operator_id == other.id
