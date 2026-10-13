"""Task HTTP contracts and isolated SQLite transaction fixtures."""
from uuid import UUID, uuid4
import pytest
from sqlalchemy import func, select
from app.overseas.auth.models import Member, MemberRole
from app.overseas.tasks.models import Task, TaskSku, TaskEvent, TaskRequest, TaskOutbox
from test_overseas_auth import overseas, seed, login, HEADERS, MEMBER

ROOT = '/api/overseas/v1'


def add_member(factory, roles=('designer',), status='active', name='候选设计'):
    with factory.begin() as session:
        member = Member(corp_id='corp', provider_user_id=uuid4().hex, name=name,
                        department='设计部', status=status)
        session.add(member)
        session.flush()
        session.add_all([MemberRole(user_id=member.id, role=role) for role in roles])
        return member.id


def payload(designer):
    return dict(name=' 图需 ', productName='手机', brand='品牌', platform='Amazon', market='美国',
                remarks='说明', skus=[{'code': ' A '}, {'code': 'B'}], designerId=str(designer))


def create(client, body, key='create-key'):
    return client.post(ROOT + '/tasks', json=body, headers={**HEADERS, 'Idempotency-Key': key})


def counts(factory):
    with factory() as session:
        return [session.scalar(select(func.count()).select_from(model))
                for model in (Task, TaskSku, TaskEvent, TaskRequest, TaskOutbox)]


def setup(overseas, roles=('operator',)):
    client, factory, _ = overseas
    actor = seed(factory, roles=roles)
    designer = add_member(factory)
    assert login(client).status_code == 200
    return client, factory, actor, designer


def test_create_replay_detail_and_outbox(overseas):
    client, factory, actor, designer = setup(overseas)
    body = payload(designer)
    first = create(client, body)
    assert first.status_code == 201, first.text
    data = first.json()
    assert data['name'] == '图需' and data['skus'] == [{'code': 'A'}, {'code': 'B'}]
    assert data['status'] == 'created' and data['version'] == 1
    assert data['createdBy']['id'] == str(actor) and data['designer']['eligible']
    assert data['capabilities'] == ['task.read', 'task.materials.submit']
    assert data['events'][0]['kind'] == 'task.created'
    second = create(client, body)
    assert second.status_code == 200 and second.json() == data
    assert create(client, {**body, 'name': '不同'}).status_code == 409
    assert counts(factory) == [1, 2, 1, 1, 1]
    with factory() as session:
        assert session.scalar(select(TaskOutbox)).published_at is None
    assert client.get(ROOT + '/tasks/' + data['id']).json() == data


@pytest.mark.parametrize('change', [
    {'name': ' '}, {'name': 'x' * 81}, {'skus': []}, {'skus': [{'code': ' '} ]},
    {'skus': [{'code': 'A'}, {'code': ' a '}]}, {'skus': [{'code': 'x', 'color': 'red'}]},
    {'skus': [{'code': str(i)} for i in range(101)]}, {'createdBy': str(uuid4())},
    {'status': 'analyzing'}, {'version': 1}, {'files': []}, {'platform': 'invalid'},
])
def test_invalid_body_is_atomic(overseas, change):
    client, factory, _, designer = setup(overseas)
    assert create(client, {**payload(designer), **change}).status_code == 422
    assert counts(factory) == [0] * 5


@pytest.mark.parametrize('roles,status', [(('operator',), 'active'), (('operator_manager',), 'active'),
                                          (('designer',), 'disabled'), ((), 'active')])
def test_invalid_candidate(overseas, roles, status):
    client, factory, _, _ = setup(overseas)
    designer = add_member(factory, roles, status)
    assert create(client, payload(designer)).status_code == 422
    assert counts(factory) == [0] * 5


def test_missing_candidate_and_key_and_browser_protection(overseas):
    client, factory, _, designer = setup(overseas)
    assert create(client, payload(uuid4())).status_code == 404
    body = payload(designer)
    assert client.post(ROOT + '/tasks', json=body, headers=HEADERS).status_code == 422
    assert create(client, body, ' ').status_code == 422
    assert create(client, body, 'x' * 129).status_code == 422
    assert client.post(ROOT + '/tasks', json=body, headers={'Idempotency-Key': 'x'}).status_code == 403
    assert counts(factory) == [0] * 5


@pytest.mark.parametrize('roles,allowed', [(('operator',), True), (('operator_manager',), True),
    (('designer',), False), (('design_manager',), False), (('super_admin',), True)])
def test_create_role_matrix(overseas, roles, allowed):
    client, factory, _, designer = setup(overseas, roles)
    assert create(client, payload(designer)).status_code == (201 if allowed else 403)


def test_candidate_search_pagination_and_minimal_fields(overseas):
    client, factory, _, _ = setup(overseas)
    add_member(factory, ('design_manager',), name='主管')
    add_member(factory, ('super_admin',), name='不可选')
    add_member(factory, ('designer',), 'disabled', name='不可选')
    pages = [client.get(ROOT + f'/task-designers?page={page}&pageSize=1').json() for page in (1, 2)]
    assert pages[0]['total'] == pages[1]['total'] == 3
    assert pages[0]['items'][0]['id'] != pages[1]['items'][0]['id']
    assert set(pages[0]['items'][0]) == {'id', 'name', 'department'}
    assert client.get(ROOT + '/task-designers?search=主管').json()['total'] == 1
    assert client.get(ROOT + '/task-designers?search=无匹配').json()['items'] == []


def test_fault_rolls_back_all_five_tables(overseas, monkeypatch):
    from app.overseas.tasks import service
    client, factory, _, designer = setup(overseas)
    original = service.request_record

    def fail(*args):
        original(*args)
        args[0].flush()
        raise RuntimeError('injected transaction failure')

    monkeypatch.setattr(service, 'request_record', fail)
    with pytest.raises(RuntimeError, match='injected'):
        create(client, payload(designer))
    assert counts(factory) == [0] * 5
