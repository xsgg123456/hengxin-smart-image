from uuid import UUID, uuid4

from app.resource_models import UserRecord
from app.modules.tasks.models import TaskRecord
from test_tasks import task_env, body, submit
from files_helpers import files_env


def test_scope_uses_authenticated_identity_before_pagination(task_env):
    client, factory, _, identity = task_env
    owner_id = identity[0]
    data = body(task_env)
    own = [submit(task_env, data, key=f'own-{i}').json()['taskId'] for i in range(3)]
    other_task = submit(task_env, data, key='other').json()['taskId']
    with factory.begin() as session:
        other = UserRecord(id=uuid4(), name='另一位同事', role='operator', status='active', identity_source='development')
        session.add(other)
        session.flush()
        session.get(TaskRecord, UUID(other_task)).owner_id = other.id
        other_id = other.id
    pages = [client.get(f'/api/v1/tasks?scope=mine&page={page}&pageSize=2').json() for page in [1, 2]]
    assert pages[0]['total'] == pages[1]['total'] == 3
    assert pages[0]['stats']['total'] == pages[0]['stats']['processing'] == 3
    assert {task['id'] for page in pages for task in page['items']} == set(own)
    assert all(task['ownerName'] == '测试操作者' for page in pages for task in page['items'])
    assert client.get('/api/v1/tasks').json()['total'] == 4
    assert client.get(f'/api/v1/tasks/{other_task}').status_code == 200
    identity[0] = other_id
    result = client.get(f'/api/v1/tasks?scope=mine&ownerId={owner_id}').json()
    assert result['total'] == result['stats']['total'] == 1
    assert result['items'][0]['id'] == other_task
    assert result['items'][0]['ownerName'] == '另一位同事'
    assert client.get('/api/v1/tasks?scope=invalid').status_code == 422
    assert client.get('/api/v1/tasks?scope=mine&search=不匹配').json()['total'] == 0
