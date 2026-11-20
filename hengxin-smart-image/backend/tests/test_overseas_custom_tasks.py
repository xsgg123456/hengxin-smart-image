from uuid import UUID

from sqlalchemy import select

from app.overseas.auth.models import Member
from app.overseas.tasks import service
from app.overseas.tasks.models import Task
from app.overseas.tasks.schemas import CreateCustomTask
from test_overseas_auth import HEADERS, overseas
from test_overseas_tasks import ROOT, counts, create, payload, setup


def custom(client, value, key='custom', **extra):
    return client.post(ROOT + '/tasks/custom', json={'productNameSku': value, **extra},
                       headers={**HEADERS, 'Idempotency-Key': key})


def test_search_by_full_custom_task_name(overseas):
    client, _, _, _ = setup(overseas)
    name = '灯' * 80 + '+' + 'S' * 80
    created = custom(client, name)
    assert created.status_code == 201
    result = client.get(ROOT + '/tasks', params={'search': name, 'designType': 'custom'})
    assert result.status_code == 200
    assert [row['id'] for row in result.json()['items']] == [created.json()['id']]


def test_custom_task_creates_once_and_opens_studio(overseas):
    client, factory, actor, _ = setup(overseas)
    first = custom(client, '  落地灯 +  A-100  ')
    assert first.status_code == 201, first.text
    task = first.json()
    assert task['name'] == '落地灯+A-100'
    assert task['productName'] == '落地灯' and task['skus'] == [{'code': 'A-100'}]
    assert task['designType'] == 'custom' and task['status'] == task['workflow'] == 'studio'
    assert task['createdBy']['id'] == task['designer']['id'] == str(actor)
    assert task['brand'] == task['platform'] == task['market'] == '' and task['language'] is None
    assert task['capabilities'] == ['task.read', 'task.design']
    assert task['requirementsReviews'] == [] and task['events'][0]['kind'] == 'task.custom_created'
    replay = custom(client, '落地灯+A-100')
    assert replay.status_code == 200 and replay.json() == task
    assert custom(client, '台灯+A-100').status_code == 409
    assert counts(factory) == [1, 1, 1, 1, 1]
    studio = client.get(ROOT + '/tasks/' + task['id'] + '/studio')
    assert studio.status_code == 200
    view = studio.json()
    assert len(view['conversations']) == 1 and view['conversationId'] == view['conversations'][0]['id']
    with factory() as session:
        row = session.scalar(select(Task))
        assert row.requirements_approved and not row.material_ids


def test_custom_validation_and_permission(overseas):
    client, factory, actor, _ = setup(overseas)
    for value in ('', '+', '落地灯', '+SKU', '落地灯+  ', 'A+B+C', 'A+' + 'x' * 81, 'A\0+X'):
        assert custom(client, value).status_code == 422
    for extra in ('platform', 'brand', 'designerId', 'materialIds', 'skillId', 'language'):
        assert custom(client, '灯+SKU', **{extra: 'forged'}).status_code == 422
    with factory.begin() as session:
        session.get(Member, actor).status = 'disabled'
    assert custom(client, '灯+SKU').status_code in (401, 403)
    assert counts(factory) == [0] * 5


def test_custom_list_filter_visibility_and_same_sku_independent(overseas):
    client, factory, actor, other = setup(overseas)
    ids = {custom(client, '灯+ABC', key).json()['id'] for key in ('one', 'two')}
    assert len(ids) == 2
    platform = create(client, {**payload(actor), 'productName': '灯'}).json()
    assert platform['designType'] == 'platform'
    with factory() as session:
        hidden, _ = service.create_task(session, session.get(Member, other),
                                        CreateCustomTask(productNameSku='灯+ABC'), 'private')
    assert client.get(ROOT + '/tasks/' + hidden['id']).status_code == 403
    def matches(kind, term):
        page = client.get(ROOT + '/tasks', params={'designType': kind, 'search': term}).json()
        return {row['id'] for row in page['items']}
    assert matches('custom', '灯') == matches('custom', 'abc') == ids
    assert matches('platform', '灯') == matches('Amazon', '灯') == {platform['id']}


def test_shopee_preserved_on_read_and_blocked_on_new_selection(overseas):
    client, factory, actor, _ = setup(overseas)
    body = payload(actor)
    assert create(client, {**body, 'platform': 'Shopee'}).status_code == 422
    task = create(client, body).json()
    task_id = UUID(task['id'])
    with factory.begin() as session:
        session.get(Task, task_id).status = 'returned'
    attempted = client.post(ROOT + '/tasks/' + task['id'] + '/resubmit',
        json={**body, 'platform': 'Shopee', 'materialIds': [task['id']], 'version': 1},
        headers={**HEADERS, 'Idempotency-Key': 'retired'})
    assert attempted.status_code == 422 and '虾皮' in attempted.text
    with factory.begin() as session:
        session.get(Task, task_id).platform = 'Shopee'
    history = client.get(ROOT + '/tasks', params={'designType': 'Shopee'}).json()
    assert history['items'][0]['platform'] == 'Shopee'
    assert history['items'][0]['designType'] == 'platform'
