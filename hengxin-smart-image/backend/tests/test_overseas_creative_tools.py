"""Exercise the overseas creative-entry API with isolated members and data."""
from uuid import UUID
import pytest
from sqlalchemy import select, func

from app.core.config import get_settings
from app.overseas.auth.models import Member
from app.overseas.studio.models import Conversation
from app.overseas.tasks import service
from app.overseas.tasks.models import Task
from app.overseas.tasks.schemas import PlatformToolTask
from test_overseas_assignment import change_roles
from test_overseas_custom_tasks import custom
from test_overseas_tasks import overseas, ROOT, HEADERS, counts, create, payload, setup


def post_tool(client, body, key='tool-create'):
    return client.post(ROOT + '/tasks/creative-tools', json=body, headers={**HEADERS, 'Idempotency-Key': key})


def body(key='outon'):
    if key == 'custom-size':
        return dict(toolKey=key, productNameSku=' 灯 + SKU-987 ')
    return dict(toolKey=key, productName=' 灯 ', sku=' SKU-987 ', language='fr')


@pytest.mark.parametrize('key,platform,brand', [
    ('outon', 'Amazon', 'OUTON'), ('outonlife', 'Amazon', 'OUTONLIFE'), ('beleev', 'Amazon', 'BELEEV'),
    ('wayfair', 'Wayfair', ''), ('walmart', 'Walmart', ''), ('home-depot', 'The Home Depot', ''),
    ('mercado-libre', 'Mercado Libre', ''), ('custom-size', '', '')])
def test_entry_metadata_idempotency_and_single_conversation(overseas, key, platform, brand):
    client, factory, actor, _ = setup(overseas, ('non_designer',))
    first = post_tool(client, body(key))
    assert first.status_code == 201, first.text
    task = first.json()
    assert (task['platform'], task['brand'], task['toolKey']) == (platform, brand, key)
    assert task['name'] == '灯+SKU-987' and task['productName'] == '灯' and task['skus'] == [{'code': 'SKU-987'}]
    assert task['creatorIdentity'] == 'non_designer' and task['capabilities'] == ['task.read', 'task.design']
    assert task['createdBy']['id'] == task['designer']['id'] == str(actor) and task['designer']['eligible']
    assert task['status'] == task['workflow'] == 'studio'
    assert task['language'] == (None if key == 'custom-size' else 'fr')
    replay = post_tool(client, body(key))
    assert replay.status_code == 200 and replay.json() == task
    assert post_tool(client, body('beleev' if key == 'outon' else 'outon')).status_code == 409
    assert counts(factory) == [1] * 5
    view = client.get(ROOT + '/tasks/' + task['id'] + '/studio')
    assert view.status_code == 200, view.text
    assert [c['id'] for c in view.json()['conversations']] == [view.json()['conversationId']]


def test_validation_blocks_forged_metadata_and_malformed_forms(overseas):
    client, factory, _, _ = setup(overseas)
    for fields in ({'sku': ' '}, {'language': 'it'}, {'brand': 'OUTONLIFE'}, {'platform': 'Walmart'},
                   {'toolKey': 'unknown'}, {'creatorIdentity': 'designer'}, {'sku': 'x\0x'},
                   {'toolKey': 'custom-size'}):
        assert post_tool(client, {**body(), **fields}).status_code == 422
    for value in ('', 'lamp+', '+SKU', 'a+b+c'):
        assert post_tool(client, {'toolKey': 'custom-size', 'productNameSku': value}).status_code == 422
    assert counts(factory) == [0] * 5


def test_role_changes_existing_sessions_and_my_tools_filter_overseas(overseas):
    client, factory, actor, other = setup(overseas, ('design_manager',))
    old = create(client, payload(actor)).json()
    legacy_custom = custom(client, '灯+SKU-987').json()
    own = post_tool(client, body()).json()
    with factory() as session:
        foreign, _ = service.create_task(session, session.get(Member, other), PlatformToolTask(**body()), 'foreign')
    with factory.begin() as session:
        session.get(Task, UUID(foreign['id'])).designer_id = actor
    for task in (old, legacy_custom, own):
        assert task['creatorIdentity'] == 'designer'
    for search_field in ('search', 'keyword'):
        page = client.get(ROOT + '/tasks', params={'toolScope': 'mine', search_field: '987'}).json()
        assert [item['id'] for item in page['items']] == [own['id']]
    assert client.get(ROOT + '/tasks?toolScope=mine&search=missing').json()['total'] == 0
    change_roles(factory, actor, ('non_designer',))
    get_settings().full_access_member_ids = get_settings().workflow_collaborator_member_ids = {actor}
    assert set(client.get(ROOT + '/auth/me').json()['capabilities']) == {'task.read', 'task.design', 'task.tool.create'}
    assert create(client, payload(actor)).status_code == custom(client, '灯+SKU').status_code == 403
    assert client.get(ROOT + '/members').status_code == 403
    page = client.get(ROOT + '/tasks').json()
    assert [(item['id'], item['creatorIdentity']) for item in page['items']] == [(own['id'], 'designer')]
    assert client.get(ROOT + '/tasks/' + own['id'] + '/studio').status_code == 200
    for task in (old, legacy_custom, foreign):
        for suffix in ('', '/studio', '/studio/transcript', '/jobs', '/materials'):
            assert client.get(ROOT + '/tasks/' + task['id'] + suffix).status_code == 403


def test_assign_non_designer_and_unknown_admin_snapshot(overseas):
    client, _, _, other = setup(overseas, ('super_admin',))
    assert post_tool(client, body()).json()['creatorIdentity'] is None
    url = ROOT + '/members/' + str(other)
    response = client.patch(url, headers=HEADERS, json={'roles': ['non_designer'], 'status': 'active', 'version': 1})
    assert response.status_code == 200 and response.json()['roles'] == ['non_designer']
    assert client.get(ROOT + '/members?role=non_designer').json()['items'][0]['id'] == str(other)


def test_failure_rolls_back_task_and_its_conversation(overseas, monkeypatch):
    client, factory, _, _ = setup(overseas)
    def fail(*_args):
        raise RuntimeError('模拟创建事务失败')
    with monkeypatch.context() as patch:
        patch.setattr(service, 'record_change', fail)
        with pytest.raises(RuntimeError, match='创建事务失败'):
            post_tool(client, body())
    assert counts(factory) == [0] * 5
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 0
    assert post_tool(client, body()).status_code == 201
