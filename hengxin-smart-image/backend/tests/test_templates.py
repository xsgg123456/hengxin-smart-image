from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.modules.templates.models import TemplateImageRecord, TemplateRecord, TemplateVersionRecord
from app.resource_models import DeletionRecord, FileRecord, UserRecord
from files_helpers import files_env
from test_files import upload


def payload(client, **updates):
    body = dict(name='模板一', mode='wallpaper', images=[upload(client).json()],
                skillVersionId=None, active=True, notes='原备注')
    body.update(updates)
    return body


def test_draft_version_order_snapshot_and_conflict(files_env):
    client, factory, store, _ = files_env
    body = payload(client)
    second = upload(client, name='第二张.png').json()
    body['images'].append(second)
    body['images'][0].update(name='恶意名称', url='https://forged.invalid')
    response = client.post('/api/v1/templates', json=body)
    assert response.status_code == 200, response.text
    original = response.json()
    assert original['images'][0]['name'] == '素材.png'
    assert original['images'][0]['url'].startswith('/api/v1/files/')
    assert not original['active'] and original['skillVersionId'] is None
    assert original['skillBinding'] == 'module_default'
    path = '/api/v1/templates/' + original['id']
    assert client.put(path, json=body).status_code == 422
    update = {**body, 'name': '改名', 'notes': '新备注', 'expectedVersion': 1,
              'images': list(reversed(body['images']))}
    current = client.put(path, json=update).json()
    assert current['version'] == 2 and current['images'][0] == second
    assert client.put(path, json=update).status_code == 409
    history = client.get(path + '/versions').json()
    assert history == [current, original]
    assert client.get(path).json() == current
    with factory() as session:
        assert len(session.scalars(select(TemplateVersionRecord)).all()) == 2
        assert len(session.scalars(select(TemplateImageRecord)).all()) == 4
    assert len(store.objects) == 2


@pytest.mark.parametrize('role', ['super_admin', 'design_manager', 'designer', 'operator'])
def test_shared_edit_delete_audit_retains_versions_and_files(files_env, role):
    client, factory, store, identity = files_env
    body = payload(client)
    original = client.post('/api/v1/templates', json=body).json()
    with factory.begin() as session:
        other = UserRecord(id=uuid4(), name='其他成员', role=role, status='active', identity_source='development')
        session.add(other)
        identity[0] = other.id
    path = '/api/v1/templates/' + original['id']
    assert client.get(path).status_code == 200
    changed = client.put(path, json={**body, 'expectedVersion': 1, 'active': False})
    assert changed.status_code == 200
    assert changed.json()['ownerId'] == original['ownerId']
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404
    assert client.get(path + '/versions').status_code == 404
    assert client.get('/api/v1/templates').json()['total'] == 0
    assert client.delete(path).status_code == 404
    with factory() as session:
        assert session.get(TemplateRecord, UUID(original['id'])).deleted_at
        receipt = session.scalar(select(DeletionRecord))
        assert receipt.operator_id == identity[0] and receipt.resource_type == 'template'
        assert len(session.scalars(select(TemplateVersionRecord)).all()) == 2
        assert len(session.scalars(select(FileRecord)).all()) == 1
    assert len(store.objects) == 1


@pytest.mark.parametrize('change', [
    {'name': ' '}, {'name': 'a' * 201}, {'images': []}, {'mode': 'text'},
    {'images': [{'name': 'x', 'url': 'https://example.com'}]},
    {'images': [{'name': 'x', 'url': 'x', 'fileId': 'not-uuid'}]},
    {'images': [{'name': 'x', 'url': 'x', 'fileId': str(uuid4())}]},
])
def test_invalid_template_rejected(files_env, change):
    client, factory, _, _ = files_env
    assert client.post('/api/v1/templates', json=payload(client, **change)).status_code == 422
    with factory() as session:
        assert session.scalar(select(TemplateRecord)) is None


@pytest.mark.parametrize('state', ['staging', 'failed', 'deleted'])
def test_unready_files_rejected(files_env, state):
    client, factory, _, _ = files_env
    body = payload(client)
    with factory.begin() as session:
        file = session.get(FileRecord, UUID(body['images'][0]['fileId']))
        if state == 'deleted':
            from app.models import utcnow
            file.deleted_at = utcnow()
        else:
            file.status = state
    assert client.post('/api/v1/templates', json=body).status_code == 422


def test_count_pagination_search_sort_and_type_filter(files_env):
    client, _, _, _ = files_env
    body = payload(client)
    assert client.post('/api/v1/templates', json={**body, 'images': body['images'] * 21}).status_code == 422
    for name, mode, count in [('Beta', 'wallpaper', 1), ('Alpha', 'product', 20), ('100%', 'wallpaper', 2)]:
        assert client.post('/api/v1/templates', json={**body, 'name': name, 'mode': mode,
                                                     'images': body['images'] * count}).status_code == 200
    page = client.get('/api/v1/templates?sort=name&page=2&pageSize=1').json()
    assert page['total'] == 3 and page['items'][0]['name'] == 'Alpha'
    assert client.get('/api/v1/templates?sort=images').json()['items'][0]['name'] == 'Alpha'
    assert client.get('/api/v1/templates?mode=product').json()['total'] == 1
    assert client.get('/api/v1/templates?search=%25').json()['total'] == 1
    assert client.get('/api/v1/templates?search=missing').json()['items'] == []
    assert client.get('/api/v1/templates?activeOnly=true').json()['total'] == 0
    assert client.get('/api/v1/templates?pageSize=101').status_code == 422


@pytest.mark.parametrize('status', ['disabled', 'pending'])
def test_invalid_identity_cannot_access_templates(files_env, status):
    client, factory, _, identity = files_env
    body = payload(client)
    template = client.post('/api/v1/templates', json=body).json()
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).status = status
    path = '/api/v1/templates/' + template['id']
    assert client.get('/api/v1/templates').status_code == 403
    assert client.get(path).status_code == 403
    assert client.get(path + '/versions').status_code == 403
    assert client.put(path, json={**body, 'expectedVersion': 1}).status_code == 403
    assert client.delete(path).status_code == 403
    assert client.post('/api/v1/templates', json=body).status_code == 403
