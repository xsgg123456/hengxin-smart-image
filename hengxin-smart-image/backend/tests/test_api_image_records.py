"""Record scopes use server identity and retain shared-resource permissions."""
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event

from app.main import app
from app.modules.api_image_edits.models import ApiFile, ApiItem, ApiTask
from app.modules.api_image_edits.presentation import list_tasks
from app.modules.auth.dependencies import get_identity_id
from app.resource_models import UserRecord
from files_helpers import files_env

ROOT = '/api/v1/api-image-edits'
ZERO = dict(tasks=0, pendingTasks=0, successImages=0, failedImages=0)


def add_user(factory, name='重名创建人', status='active'):
    user_id = uuid4()
    with factory.begin() as session:
        session.add(UserRecord(id=user_id, name=name, role='operator', status=status,
                               identity_source='development'))
    return user_id


def add_task(factory, owner, *, created='2026-10-21T16:00:00+00:00',
             state='succeeded', states=('succeeded',), name='记录', deleted=False,
             operator=None, task_id=None):
    task_id, file_id = task_id or uuid4(), uuid4()
    timestamp = datetime.fromisoformat(created)
    with factory.begin() as session:
        session.add(ApiFile(id=file_id, owner_id=owner, name='图.png', bucket='test',
            object_key=str(file_id), content_type='image/png', checksum='0' * 64,
            size_bytes=1, width=8, height=6))
        session.flush()
        session.add(ApiTask(id=task_id, owner_id=owner, operator_id=operator or owner,
            name=name, prompt='不应出现在汇总中的大提示词' * 500, material_id=file_id,
            parameters={}, state=state, created_at=timestamp,
            deleted_at=timestamp if deleted else None))
        session.flush()
        session.add_all([ApiItem(id=uuid4(), task_id=task_id, source_id=file_id,
            position=position, state=item_state) for position, item_state in enumerate(states, 1)])
    return str(task_id)


def records(client, **params):
    response = client.get(ROOT + '/tasks', params={'view': 'summary', **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_default_owner_all_other_and_identity_switch(files_env):
    client, factory, _, identity = files_env
    mine, other = identity[0], add_user(factory)
    mine_id = add_task(factory, mine, operator=other)
    other_id = add_task(factory, other, operator=mine)
    assert [row['id'] for row in records(client)['items']] == [mine_id]
    assert records(client)['items'][0]['creatorId'] == str(mine)
    assert records(client, scope='all')['total'] == 2
    filtered = records(client, scope='all', creatorId=str(other))
    assert [row['id'] for row in filtered['items']] == [other_id]
    assert filtered['stats']['tasks'] == 1
    assert client.get(ROOT + '/tasks/' + other_id).status_code == 200
    assert records(client, view='detail')['items'][0]['creatorId'] == str(mine)
    with factory() as session:
        assert list_tasks(session, 1, 20, '', '')['total'] == 2
    identity[0] = other
    assert [row['id'] for row in records(client)['items']] == [other_id]


def test_creators_include_disabled_history_current_and_use_ids(files_env):
    client, factory, _, identity = files_env
    first, second = add_user(factory), add_user(factory, status='disabled')
    removed, unused = add_user(factory, '仅已删除'), add_user(factory, '没有任务')
    first_id = add_task(factory, first)
    second_id = add_task(factory, second)
    add_task(factory, removed, deleted=True)
    response = client.get(ROOT + '/creators')
    assert response.status_code == 200, response.text
    rows = response.json()['items']
    assert {row['id'] for row in rows} == {str(identity[0]), str(first), str(second)}
    assert all(set(row) == {'id', 'name'} for row in rows)
    assert [row['id'] for row in records(client, scope='all', creatorId=str(first))['items']] == [first_id]
    assert [row['id'] for row in records(client, scope='all', creatorId=str(second))['items']] == [second_id]
    assert records(client, scope='all', creatorId=str(unused))['stats'] == ZERO


def test_beijing_dates_inclusive_start_exclusive_next_day(files_env):
    client, factory, _, identity = files_env
    before = add_task(factory, identity[0], created='2026-10-21T15:59:59.999999+00:00')
    start = add_task(factory, identity[0], created='2026-10-21T16:00:00+00:00')
    end = add_task(factory, identity[0], created='2026-10-22T15:59:59.999999+00:00')
    after = add_task(factory, identity[0], created='2026-10-22T16:00:00+00:00')
    result = records(client, dateFrom='2026-10-22', dateTo='2026-10-22')
    assert [row['id'] for row in result['items']] == [end, start]
    assert result['stats']['tasks'] == result['stats']['successImages'] == 2
    assert {row['id'] for row in records(client, dateFrom='2026-10-22')['items']} == {start, end, after}
    assert {row['id'] for row in records(client, dateTo='2026-10-22')['items']} == {before, start, end}


def test_stats_match_full_filter_not_page_and_deleted_excluded(files_env):
    client, factory, _, identity = files_env
    for state in ['queued', 'running', 'uncertain', 'failed', 'succeeded']:
        add_task(factory, identity[0], state=state, states=('succeeded', 'succeeded', 'failed'), name='匹配记录')
    add_task(factory, identity[0], name='不匹配', states=('failed',))
    add_task(factory, identity[0], name='匹配记录', deleted=True, state='queued', states=('failed',) * 9)
    add_task(factory, add_user(factory), name='匹配记录', states=('failed',) * 7)
    expected = dict(tasks=5, pendingTasks=3, successImages=10, failedImages=5)
    first = records(client, search='匹配记录', pageSize=2)
    second = records(client, search='匹配记录', pageSize=2, page=2)
    assert first['stats'] == second['stats'] == expected
    assert first['total'] == second['total'] == 5
    assert len(first['items']) == len(second['items']) == 2
    assert not {row['id'] for row in first['items']} & {row['id'] for row in second['items']}
    beyond = records(client, search='匹配记录', pageSize=2, page=9)
    assert beyond['items'] == [] and beyond['stats'] == expected
    queued = records(client, search='匹配记录', status='queued')
    assert queued['stats'] == dict(tasks=1, pendingTasks=1, successImages=2, failedImages=1)
    assert records(client, search=queued['items'][0]['id'][:8])['total'] == 1


def test_empty_no_items_and_stable_order(files_env):
    client, factory, _, identity = files_env
    assert records(client)['stats'] == ZERO
    assert records(client)['items'] == []
    ids = [UUID(int=3), UUID(int=1), UUID(int=2)]
    for identifier in ids:
        add_task(factory, identity[0], task_id=identifier, states=())
    result = records(client)
    assert [row['id'] for row in result['items']] == [str(value) for value in sorted(ids)]
    assert result['stats'] == dict(tasks=3, pendingTasks=0, successImages=0, failedImages=0)
    assert records(client, search='完全没有匹配')['stats'] == ZERO


@pytest.mark.parametrize('params', [
    {'scope': 'unknown'}, {'creatorId': 'not-a-uuid', 'scope': 'all'},
    {'creatorId': str(uuid4())}, {'dateFrom': 'not-a-date'},
    {'dateFrom': '2026-10-23', 'dateTo': '2026-10-22'},
    {'dateFrom': '0001-01-01'},
    {'page': 0}, {'pageSize': 101},
])
def test_invalid_filters_are_422(files_env, params):
    client, _, _, _ = files_env
    assert client.get(ROOT + '/tasks', params=params).status_code == 422


@pytest.mark.parametrize('endpoint', ['/tasks', '/creators'])
def test_login_and_shared_permission_required(files_env, endpoint):
    client, factory, _, identity = files_env
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).status = 'disabled'
    assert client.get(ROOT + endpoint).status_code == 403
    identity[0] = uuid4()
    assert client.get(ROOT + endpoint).status_code == 401
    app.dependency_overrides.pop(get_identity_id)
    assert client.get(ROOT + endpoint).status_code == 401


def test_aggregate_does_not_load_task_or_item_payloads(files_env):
    client, factory, _, identity = files_env
    for _ in range(4):
        add_task(factory, identity[0], states=('succeeded', 'failed'))
    statements = []
    engine = factory.kw['bind']
    def capture(conn, cursor, statement, *args):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        result = records(client, pageSize=1)
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert result['stats'] == dict(tasks=4, pendingTasks=0, successImages=4, failedImages=4)
    assert len(result['items']) == 1
    assert not any('api_image_tasks.prompt' in sql or 'api_image_versions' in sql
                   or 'api_image_tasks.events' in sql or 'api_image_items.result_bytes,' in sql
                   for sql in statements)
