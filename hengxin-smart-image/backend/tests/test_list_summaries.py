from uuid import UUID

from sqlalchemy import event, select

from app.execution.fixture_runner import run_generation
from app.modules.api_image_edits.models import ApiItem, ApiTask
from app.modules.tasks.models import TaskRecord
from app.modules.tasks.queries import serialize
from files_helpers import files_env
from performance_samples import sample
from test_api_image_domain import ROOT, create, enabled_api
from test_tasks import body, job_for, submit, task_env


def test_api_summary_counts_cover_and_no_history_queries(files_env):
    client, factory, _, _ = files_env
    first, payload = create(client, count=4)
    create(client, count=2)
    with factory.begin() as session:
        task = session.get(ApiTask, UUID(first))
        task.prompt = '完整提示必须只出现在详情' * 100
        items = session.scalars(select(ApiItem).where(ApiItem.task_id == task.id)
                                .order_by(ApiItem.position)).all()
        for item, state in zip(items, ['succeeded', 'failed', 'uncertain', 'collecting']):
            item.state = state
    sql = []
    engine = factory.kw['bind']
    def capture(conn, cursor, statement, *args):
        sql.append(statement)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        small, one = sample(client, ROOT + '/tasks?view=summary&pageSize=1')
        response, two = sample(client, ROOT + '/tasks?view=summary&pageSize=20')
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert one['sql_before_headers'] == two['sql_before_headers'] == 6
    assert not any('api_image_versions' in s or 'api_image_attempts' in s for s in sql)
    assert not any('api_image_tasks.prompt' in s or 'result_bytes' in s for s in sql)
    row = next(row for row in response.json()['items'] if row['id'] == first)
    assert row['counts'] == dict(total=4, success=1, failed=1, uncertain=1)
    assert row['batch'] == dict(total=1, current=1, running=1)
    assert row['cover']['fileId'] == payload['originalFileIds'][0]
    assert not {'prompt', 'items', 'events', 'metrics'} & row.keys()
    detail = client.get(ROOT + '/tasks/' + first).json()
    assert detail['prompt'] == '完整提示必须只出现在详情' * 100
    assert len(detail['items']) == 4
    # Old open browser tabs keep their contract across backend-first rollout.
    legacy = client.get(ROOT + '/tasks').json()['items']
    assert next(row for row in legacy if row['id'] == first)['prompt'] == detail['prompt']


def test_cli_batch_preserves_contract_and_constant_sql(task_env):
    client, factory, _, _ = task_env
    for index in range(4):
        response = submit(task_env, {**body(task_env, 'wallpaper'), 'name': f'列表{index}'},
                          f'batch-list-{index}')
        assert response.status_code == 202
        run_generation(job_for(factory, response.json()), factory, task_env[2])
    one, small = sample(client, '/api/v1/tasks?pageSize=1')
    many, large = sample(client, '/api/v1/tasks?pageSize=20')
    assert small['sql_before_headers'] == large['sql_before_headers'] == 16
    assert one.json()['total'] == many.json()['total'] == 4
    assert one.json()['stats'] == many.json()['stats']
    for item in many.json()['items']:
        with factory() as session:
            original = serialize(session, session.get(TaskRecord, UUID(item['id'])))
            assert item == original.model_dump(mode='json')
