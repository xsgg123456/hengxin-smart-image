"""Permission-scoped people statistics, archive actors and task filters."""
from datetime import datetime, timezone
from uuid import UUID

from app.overseas.auth.models import Member
from app.overseas.execution.queue import enqueue
from app.overseas.tasks.models import Task, TaskDeletion, TaskSku
from test_overseas_assignment import change_roles
from test_overseas_management_operators import studio_job
from test_overseas_tasks import ROOT, add_member, create, overseas, payload, setup
from test_overseas_materials import materials  # noqa: F401
from test_overseas_studio import send, studio  # noqa: F401
from test_overseas_plans import post


def test_actual_send_replay_cancel_and_new_request_are_counted(studio):
    client, _, actor, task, _, _ = studio
    first = send(client, task, key='light-send')
    assert first.status_code == 200
    turn = first.json()['turns'][0]
    assert send(client, task, key='light-send').json()['turns'][0]['id'] == turn['id']
    assert client.get(ROOT + '/management/people').json()['items'][0]['calls'] == 1
    cancelled = post(client, task, '/studio/turns/' + turn['id'] + '/cancel', {'version': 1})
    assert cancelled.status_code == 200 and cancelled.json()['turns'][0]['status'] == 'cancelled'
    assert client.get(ROOT + '/management/people').json()['items'][0]['calls'] == 1
    second = send(client, task, key='light-new', text='重新发起')
    assert second.status_code == 200 and len(second.json()['turns']) == 2
    people = client.get(ROOT + '/management/people').json()['items']
    assert len(people) == 1 and people[0]['id'] == str(actor) and people[0]['calls'] == 2
    assert client.get(ROOT + f'/management/jobs?memberId={actor}').json()['total'] == 2


def test_people_counts_requests_not_claims_and_preserves_scopes(overseas):
    client, factory, actor, designer = setup(overseas, ('super_admin',))
    task_id = UUID(create(client, payload(designer)).json()['id'])
    other = add_member(factory, name='另一个执行人')
    with factory.begin() as session:
        one = studio_job(session, task_id, designer, 'light-one')
        two = studio_job(session, task_id, designer, 'light-two')
        three = studio_job(session, task_id, other, 'light-three')
        unknown = enqueue(session, task_id, 'analysis', 'light-legacy', {})
        one.status, one.execution_count = 'queued', 0
        two.status, two.execution_count = 'failed', 7
        three.status, three.execution_count = 'collecting', 1
        for job in (one, two, three, unknown):
            job.created_at = datetime(2026, 11, 7, 1, tzinfo=timezone.utc)
        session.get(Member, other).status = 'disabled'
    management = ROOT + '/management'
    people = client.get(management + '/people').json()['items']
    assert {item['id']: (item['calls'], item['images']) for item in people} == {
        str(designer): (2, 2), str(other): (1, 1)}
    assert all(item['lastCall'] for item in people)
    assert client.get(management + f'/people?memberId={designer}').json()['items'][0]['calls'] == 2
    assert client.get(management + '/people?from=2026-11-07T01:00:00Z&before=2026-11-07T01:00:01Z').json()['items'] == people
    assert client.get(management + '/people?from=2026-11-07T09:00:00%2B08:00&before=2026-11-07T09:00:01%2B08:00').json()['items'] == people
    assert client.get(management + '/people?before=2026-11-07T01:00:00Z').json()['items'] == []
    assert client.get(management + '/jobs').json()['total'] == 4
    assert client.get(management + '/jobs?statusGroup=running').json()['total'] == 1
    assert client.get(management + '/jobs?search=图需').json()['total'] == 4
    assert client.get(management + '/jobs?search=' + str(task_id)).json()['total'] == 4
    assert client.get(management + '/jobs?search=无匹配').json()['total'] == 0
    assert client.get(management + '/people?from=2026-11-07T01:00:00Z&before=2026-11-07T01:00:00Z').status_code == 422
    change_roles(factory, actor, ('designer',))
    with factory.begin() as session:
        task = session.get(Task, task_id)
        task.created_by = other
        task.designer_id = other
    assert client.get(management + '/people').json()['items'] == []
    assert client.get(management + f'/jobs?memberId={designer}').json()['total'] == 0


def test_task_group_and_assignee_apply_before_count_and_pagination(overseas):
    client, factory, actor, designer = setup(overseas, ('super_admin',))
    disabled = add_member(factory, name='停用设计')
    hidden = add_member(factory, name='其他设计')
    with factory.begin() as session:
        session.get(Member, disabled).status = 'disabled'
        for i in range(25):
            task = Task(name=f'任务{i}', product_name='台灯', brand='OUTON', platform='Wayfair', market='US',
                        created_by=actor, designer_id=disabled, workflow='legacy',
                        status='reworking' if i % 2 else 'studio')
            session.add(task)
            session.flush()
            session.add(TaskSku(task_id=task.id, code=f'SKU-{i}', code_key=f'sku-{i}', position=0))
            if i == 0:
                session.add(TaskDeletion(task_id=task.id, actor_id=actor, status='delete_failed'))
        task = Task(name='其他任务', product_name='台灯', brand='OUTON', platform='Wayfair', market='US',
                    created_by=hidden, designer_id=hidden, status='studio')
        session.add(task)
        session.flush()
        session.add(TaskSku(task_id=task.id, code='HIDDEN', code_key='hidden', position=0))
        legacy = Task(name='旧流程任务', product_name='台灯', brand='OUTON', platform='Wayfair', market='US',
                      created_by=actor, designer_id=disabled, workflow='legacy', status='submitted',
                      requirements_approved=True)
        session.add(legacy)
    params = f'?designerId={disabled}&statusGroup=designing&pageSize=20'
    first = client.get(ROOT + '/tasks' + params).json()
    second = client.get(ROOT + '/tasks' + params + '&page=2').json()
    assert first['total'] == second['total'] == 24
    assert len(first['items']) == 20 and len(second['items']) == 4
    assert all(item['designer']['id'] == str(disabled) for item in first['items'] + second['items'])
    assert any(item['status'] == 'reworking' for item in first['items'] + second['items'])
    pending = client.get(ROOT + f'/tasks?designerId={disabled}&statusGroup=pending').json()
    assert pending['total'] == 1 and pending['items'][0]['status'] == 'submitted'
    assert client.get(ROOT + '/tasks?statusGroup=unknown').status_code == 422
    assert str(disabled) in {p['id'] for p in client.get(ROOT + '/task-assignees').json()['items']}
    change_roles(factory, actor, ('designer',))
    assert str(hidden) not in {p['id'] for p in client.get(ROOT + '/task-assignees').json()['items']}
    assert client.get(ROOT + f'/tasks?designerId={hidden}').json()['total'] == 0
