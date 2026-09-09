from test_tasks import task_env, body, submit, job_for
from files_helpers import files_env
from app.execution.fixture_runner import run_generation


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
