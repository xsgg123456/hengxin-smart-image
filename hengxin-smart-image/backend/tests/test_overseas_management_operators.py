from uuid import UUID, uuid4
import pytest
from app.overseas.auth.models import Member
from app.overseas.execution.queue import enqueue
from app.overseas.studio.models import Conversation, Turn, Picture
from app.overseas.tasks.models import Task
from test_overseas_tasks import overseas, setup, create, payload, add_member
from test_overseas_assignment import change_roles
from test_overseas_management import MANAGE


def studio_job(session, task_id, actor, key):
    channel = Conversation(task_id=task_id)
    session.add(channel)
    session.flush()
    job = enqueue(session, task_id, 'studio', key, {})
    turn = Turn(task_id=task_id, conversation_id=channel.id, job_id=job.id, actor_id=actor, text='private')
    session.add(turn)
    session.flush()
    session.add(Picture(task_id=task_id, turn_id=turn.id, name='test.png', content_type='image/png',
        size_bytes=1, checksum='a' * 64, bucket='test', object_key=key, width=1, height=1))
    return job


@pytest.mark.parametrize('manager', ['super_admin', 'operator_manager', 'design_manager'])
def test_actual_operator_filters_intersect_scope_and_keep_unknown_visible(overseas, manager):
    client, factory, actor, designer = setup(overseas)
    task_id = UUID(create(client, payload(designer)).json()['id'])
    other = add_member(factory, name='另一操作者')
    with factory.begin() as session:
        hidden = Task(name='other task', product_name='p', brand='b', platform='Amazon', market='US',
                      created_by=other, designer_id=other)
        session.add(hidden)
        session.flush()
        studio_job(session, task_id, designer, 'designer')
        studio_job(session, hidden.id, other, 'other')
        enqueue(session, task_id, 'analysis', 'unknown', {})
        session.get(Member, other).status = 'disabled'
    change_roles(factory, actor, (manager,))
    assert client.get(MANAGE + '/usage').json()['jobs'] == 3
    rows = client.get(MANAGE + '/jobs').json()
    assert rows['total'] == 3
    assert {row['operatorId'] for row in rows['items']} == {None, str(designer), str(other)}
    assert any(row['operatorName'] == '另一操作者' for row in rows['items'])
    assert {row['id'] for row in client.get(MANAGE + '/operators').json()['items']} == {str(designer), str(other)}
    for selected in (designer, other):
        query = '?memberId=' + str(selected)
        summary = client.get(MANAGE + '/usage' + query).json()
        assert summary['jobs'] == 1 and summary['generationImages'] == 1
        filtered = client.get(MANAGE + '/jobs' + query).json()
        assert filtered['total'] == 1 and filtered['items'][0]['operatorId'] == str(selected)
        assert filtered['items'][0]['imageCount'] == summary['generationImages']
    assert client.get(MANAGE + '/usage?memberId=' + str(uuid4())).json()['jobs'] == 0
    assert client.get(MANAGE + '/jobs?memberId=invalid').status_code == 422
    change_roles(factory, actor, ('operator',))
    assert client.get(MANAGE + '/usage').json()['jobs'] == 2
    assert client.get(MANAGE + '/usage?memberId=' + str(other)).json()['jobs'] == 0
    assert client.get(MANAGE + '/jobs?memberId=' + str(other)).json()['total'] == 0
    assert client.get(MANAGE + '/operators').json()['items'] == [{'id': str(designer), 'name': '候选设计'}]
    change_roles(factory, actor, ('designer',))
    assert client.get(MANAGE + '/usage?memberId=' + str(designer)).json()['jobs'] == 0
    assert client.get(MANAGE + '/operators').json()['items'] == []
