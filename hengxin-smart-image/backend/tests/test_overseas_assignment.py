from uuid import UUID, uuid4
import pytest
from sqlalchemy import delete, select
from app.overseas.auth.models import BusinessSession, Member, MemberRole
from app.overseas.tasks.models import Task
from test_overseas_tasks import overseas, setup, payload, create, add_member, counts, ROOT, HEADERS


def assign(client, task_id, designer, version=1, key='assignment'):
    return client.patch(ROOT + '/tasks/' + task_id + '/assignment',
        json={'designerId': str(designer), 'version': version}, headers={**HEADERS, 'Idempotency-Key': key})


def change_roles(factory, actor, roles):
    with factory.begin() as session:
        session.execute(delete(MemberRole).where(MemberRole.user_id == actor))
        session.add_all([MemberRole(user_id=actor, role=role) for role in roles])


def use_unrelated_designer(factory):
    unrelated = add_member(factory)
    with factory.begin() as session:
        for current in session.scalars(select(BusinessSession)):
            current.user_id = unrelated
    return unrelated


def test_assignment_replay_preserves_current_state_and_atomic_audit(overseas):
    client, factory, actor, first = setup(overseas, ('super_admin',))
    task = create(client, payload(first)).json()
    second, third = add_member(factory), add_member(factory)
    result = assign(client, task['id'], second)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['version'] == 2 and data['status'] == 'created' and data['skus'] == task['skus']
    assert data['events'][-1]['beforeDesignerId'] == str(first)
    assert data['events'][-1]['afterDesignerId'] == str(second)
    assert assign(client, task['id'], third).status_code == 409
    assert assign(client, task['id'], third, 1, 'stale').status_code == 409
    assert assign(client, task['id'], second, 2, 'same').status_code == 409
    assert assign(client, task['id'], third, 2, 'next').status_code == 200
    replay = assign(client, task['id'], second).json()
    assert replay['version'] == 3 and replay['designer']['id'] == str(third)
    assert create(client, payload(first)).json()['designer']['id'] == str(third)
    assert counts(factory) == [1, 2, 3, 3, 3]
    change_roles(factory, actor, ('designer',))
    assert assign(client, task['id'], second).status_code == 403


@pytest.mark.parametrize('roles,allowed', [(('designer',), False), (('design_manager',), True), (('super_admin',), True)])
def test_assignment_role_matrix(overseas, roles, allowed):
    client, factory, actor, designer = setup(overseas)
    task = create(client, payload(designer)).json()
    next_designer = add_member(factory)
    change_roles(factory, actor, roles)
    assert assign(client, task['id'], next_designer).status_code == (200 if allowed else 403)


@pytest.mark.parametrize('roles,expected', [(('designer',), 2), (('design_manager',), 3), (('super_admin',), 3)])
def test_scopes_filter_before_paging_search_and_detail(overseas, roles, expected):
    client, factory, actor, designer = setup(overseas)
    own = create(client, payload(designer), 'own').json()
    assigned = create(client, {**payload(designer), 'name': 'assigned'}, 'assigned').json()
    other = create(client, {**payload(designer), 'name': 'other'}, 'other').json()
    stranger = add_member(factory, ('designer',))
    with factory.begin() as session:
        session.get(Task, UUID(assigned['id'])).created_by = stranger
        session.get(Task, UUID(assigned['id'])).designer_id = actor
        session.get(Task, UUID(other['id'])).created_by = stranger
    change_roles(factory, actor, roles)
    response = client.get(ROOT + '/tasks?pageSize=1').json()
    assert response['total'] == expected and len(response['items']) == 1
    assert client.get(ROOT + '/tasks?search=B').json()['total'] == expected
    mine = client.get(ROOT + '/tasks?scope=mine').json()
    assert mine['total'] == min(expected, 2)
    assert client.get(ROOT + '/tasks?search=' + own['id']).json()['total'] == 1
    assert client.get(ROOT + '/tasks/' + other['id']).status_code == (200 if expected == 3 else 403)
    assert client.get(ROOT + '/tasks/' + str(uuid4())).status_code == 404


@pytest.mark.parametrize('creator_role', [False, True])
def test_old_designer_loses_access_or_only_retains_creator_read(overseas, creator_role):
    client, factory, actor, designer = setup(overseas, ('super_admin',))
    task = create(client, payload(actor)).json()
    assert 'task.design' in task['capabilities']
    assert assign(client, task['id'], designer).status_code == 200
    if not creator_role:
        with factory.begin() as session:
            session.get(Task, UUID(task['id'])).created_by = add_member(factory)
    change_roles(factory, actor, ('designer',))
    result = client.get(ROOT + '/tasks/' + task['id'])
    assert result.status_code == (200 if creator_role else 403)
    if creator_role:
        assert result.json()['capabilities'] == ['task.read', 'task.materials.submit']


def test_disabled_current_designer_can_be_replaced(overseas):
    client, factory, _, designer = setup(overseas, ('super_admin',))
    task = create(client, payload(designer)).json()
    with factory.begin() as session:
        session.get(Member, designer).status = 'disabled'
    detail = client.get(ROOT + '/tasks/' + task['id']).json()
    assert not detail['designer']['eligible'] and detail['designer']['status'] == 'disabled'
    assert assign(client, task['id'], add_member(factory)).status_code == 200


def test_assignment_fault_rolls_back_task_event_and_outbox(overseas, monkeypatch):
    from app.overseas.tasks import assignment
    client, factory, _, designer = setup(overseas, ('super_admin',))
    task = create(client, payload(designer)).json()
    original = assignment.request_record

    def fail(*args):
        original(*args)
        args[0].flush()
        raise RuntimeError('injected assignment failure')

    monkeypatch.setattr(assignment, 'request_record', fail)
    with pytest.raises(RuntimeError, match='injected'):
        assign(client, task['id'], add_member(factory))
    assert counts(factory) == [1, 2, 1, 1, 1]
    assert client.get(ROOT + '/tasks/' + task['id']).json() == task

@pytest.mark.parametrize('roles,status', [((), 'active'), (('designer',), 'disabled')])
def test_assignment_invalid_candidate_keeps_state(overseas, roles, status):
    client, factory, _, designer = setup(overseas, ('super_admin',))
    task = create(client, payload(designer)).json()
    invalid = add_member(factory, roles, status)
    assert assign(client, task['id'], invalid).status_code == 422
    assert assign(client, task['id'], uuid4()).status_code == 404
    assert counts(factory) == [1, 2, 1, 1, 1]
    assert client.get(ROOT + '/tasks/' + task['id']).json() == task


def test_new_designer_reads_after_assignment_and_loses_access_after_next(overseas):
    from test_overseas_auth import login, MEMBER
    client, factory, _, designer = setup(overseas, ('super_admin',))
    task = create(client, payload(designer)).json()
    next_designer = add_member(factory)
    assert assign(client, task['id'], next_designer).status_code == 200
    with factory() as session:
        identifier = session.get(Member, next_designer).provider_user_id
    overseas[2]['member'] = {**MEMBER, 'provider_user_id': identifier}
    assert login(client).status_code == 200
    data = client.get(ROOT + '/tasks/' + task['id']).json()
    assert data['capabilities'] == ['task.read', 'task.design']
    assert client.get(ROOT + '/task-designers').status_code == 200
