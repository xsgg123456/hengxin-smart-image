from test_tasks import task_env, body, submit, job_for
from files_helpers import files_env
from app.execution.fixture_runner import run_generation
from uuid import UUID
from app.modules.tasks.models import RoundRecord
from app.execution.observation import DELIVERY_PENDING_LABEL


def test_search_name_sku_id_and_workspace_stats(task_env):
    client, factory, store, _ = task_env
    first = submit(task_env, {**body(task_env), 'name': '文字任务', 'sku': 'AX_20%'}).json()
    second = submit(task_env, {**body(task_env, 'product'), 'name': '商品任务', 'sku': 'OTHER'}, 'two').json()
    run_generation(job_for(factory, first), factory, store)
    expected = {'total': 2, 'processing': 1, 'ready': 1, 'archived': 0}
    for search in ['文字', 'ax_20%', first['taskId'], first['taskId'][:8]]:
        result = client.get('/api/v1/tasks', params={'search': search}).json()
        assert [item['id'] for item in result['items']] == [first['taskId']]
        assert result['total'] == 1 and result['stats'] == expected
    result = client.get('/api/v1/tasks', params={'mode': 'product', 'state': 'processing', 'pageSize': 1}).json()
    assert [item['id'] for item in result['items']] == [second['taskId']]
    assert result['total'] == 1 and result['stats'] == expected
    result = client.get('/api/v1/tasks', params={'search': '不存在', 'mode': 'text'}).json()
    assert result['total'] == 0 and result['items'] == [] and result['stats'] == expected
    assert client.delete('/api/v1/tasks/' + second['taskId']).status_code == 200
    result = client.get('/api/v1/tasks').json()
    assert result['stats'] == {'total': 1, 'processing': 0, 'ready': 1, 'archived': 0}


def test_pending_delivery_list_history_filters_and_stats_are_consistent(task_env):
    client, factory, _, _ = task_env
    pending = submit(task_env, key='pending').json()
    ordinary = submit(task_env, key='ordinary').json()
    with factory.begin() as session:
        for receipt, error in [(pending, DELIVERY_PENDING_LABEL), (ordinary, None)]:
            round = session.get(RoundRecord, UUID(receipt['roundId']))
            round.status, round.error = 'uncertain', error
    listing = client.get('/api/v1/tasks').json()
    assert listing['stats']['processing'] == 1
    assert listing['stats']['ready'] == 0
    for state, expected in [('processing', pending), ('执行中', pending), ('error', ordinary), ('失败', ordinary)]:
        data = client.get('/api/v1/tasks', params={'state': state}).json()
        assert [item['id'] for item in data['items']] == [expected['taskId']]
        assert data['total'] == 1 and data['stats']['processing'] == 1
    detail = client.get('/api/v1/tasks/' + pending['taskId']).json()
    assert detail['task']['state'] == '执行中' and detail['task']['error'] is None
    assert detail['rounds'][0]['state'] == '执行中' and detail['rounds'][0]['error'] is None
    with factory.begin() as session:
        session.get(RoundRecord, UUID(pending['roundId'])).status = 'cancelled'
    detail = client.get('/api/v1/tasks/' + pending['taskId']).json()
    assert detail['task']['state'] == '失败'
    assert client.get('/api/v1/tasks').json()['stats']['processing'] == 0
