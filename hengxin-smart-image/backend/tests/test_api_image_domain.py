from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models import Job
from app.modules.api_image_edits.config import get_api_settings
from app.modules.api_image_edits.models import ApiDispatch, ApiFile, ApiItem, ApiTask
from app.resource_models import UserRecord
from files_helpers import files_env, image_bytes

ROOT = '/api/v1/api-image-edits'


@pytest.fixture(autouse=True)
def enabled_api(monkeypatch):
    monkeypatch.setenv('API_IMAGE_ENABLED', 'true')
    # Existing business tests exercise inputs/versions, not elapsed wall time.
    # Admission contract tests explicitly restore the production 5-second gate.
    monkeypatch.setenv('API_IMAGE_SEND_INTERVAL_SECONDS', '0.000001')
    get_api_settings.cache_clear()
    yield
    get_api_settings.cache_clear()


def upload(client, name='image.png'):
    result = client.post(ROOT + '/files', files={'file': (name, image_bytes(), 'image/png')})
    assert result.status_code == 200, result.text
    return result.json()


def create(client, count=2, key=None):
    originals = [upload(client, f'{i}.png') for i in range(count)]
    material = upload(client, 'material.png')
    payload = {'name': '接口换套图', 'prompt': '替换屏幕',
               'originalFileIds': [p['fileId'] for p in originals],
               'materialFileId': material['fileId']}
    result = client.post(ROOT + '/tasks', json=payload,
                         headers={'Idempotency-Key': key or str(uuid4())})
    assert result.status_code == 202, result.text
    return result.json()['taskId'], payload


def test_upload_scope_permissions_and_reference_protection(files_env):
    client, factory, store, identity = files_env
    task_id, payload = create(client)
    first = payload['originalFileIds'][0]
    response = client.get(ROOT + '/tasks/' + task_id)
    assert response.status_code == 200
    task = response.json()
    assert [i['source']['fileId'] for i in task['items']] == payload['originalFileIds']
    assert [i['position'] for i in task['items']] == [1, 2]
    assert client.get(task['items'][0]['source']['url']).content == image_bytes()
    assert client.get('/api/v1/files/' + first).status_code == 404
    assert client.delete(ROOT + '/files/' + first).status_code == 409
    with factory() as session:
        assert 'files' not in session.bind.dialect.get_table_names(session.connection())
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        assert session.scalar(select(func.count()).select_from(ApiDispatch)) == 1
    assert all(key.startswith('api-image-edits/') for key in store.objects)
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).status = 'disabled'
    assert client.get(ROOT + '/tasks').status_code == 403
    assert client.get(task['material']['url']).status_code == 403


def test_idempotent_submit_payload_conflict_and_queued_delete_protection(files_env):
    client, factory, _, _ = files_env
    task_id, payload = create(client, key='one')
    duplicate = client.post(ROOT + '/tasks', json=payload, headers={'Idempotency-Key': 'one'})
    assert duplicate.json() == {'taskId': task_id}
    payload['prompt'] = '不同提示'
    assert client.post(ROOT + '/tasks', json=payload,
                       headers={'Idempotency-Key': 'one'}).status_code == 409
    assert client.get(ROOT + '/tasks?pageSize=1&search=接口').json()['total'] == 1
    assert client.get(ROOT + '/tasks', params={'search': task_id}).json()['total'] == 1
    assert client.get(ROOT + '/tasks', params={'search': task_id[:8]}).json()['total'] == 1
    assert client.delete(ROOT + '/tasks/' + task_id).status_code == 409
    assert client.get(ROOT + '/tasks/' + task_id).status_code == 200
    assert client.get(ROOT + '/tasks').json()['total'] == 1
    with factory() as session:
        assert session.get(ApiTask, UUID(task_id)).deleted_at is None
        assert session.get(ApiDispatch, UUID(task_id)).completed_at is None


def test_unreferenced_file_delete_and_foreign_file_rejection(files_env):
    client, _, _, _ = files_env
    picture = upload(client)
    assert client.delete(ROOT + '/files/' + picture['fileId']).status_code == 200
    assert client.get(picture['url']).status_code == 404
    cli = {'fileId': str(uuid4())}
    payload = {'name': 'x', 'prompt': 'p', 'originalFileIds': [cli['fileId']],
               'materialFileId': cli['fileId']}
    assert client.post(ROOT + '/tasks', json=payload,
                       headers={'Idempotency-Key': 'foreign'}).status_code == 404


@pytest.mark.parametrize('change', [
    {'name': ' '}, {'prompt': ''}, {'originalFileIds': []},
    {'originalFileIds': [str(uuid4())] * 21}, {'extra': 'no'},
])
def test_input_validation(files_env, change):
    client, _, _, _ = files_env
    payload = {'name': 'n', 'prompt': 'p', 'originalFileIds': [str(uuid4())],
               'materialFileId': str(uuid4()), **change}
    assert client.post(ROOT + '/tasks', json=payload,
                       headers={'Idempotency-Key': 'invalid'}).status_code == 422


def test_disabled_channel_and_admin_permission(files_env, monkeypatch):
    client, factory, _, identity = files_env
    monkeypatch.setenv('API_IMAGE_ENABLED', 'false')
    get_api_settings.cache_clear()
    assert client.get(ROOT + '/status').json()['enabled'] is False
    assert client.post(ROOT + '/files', files={'file': ('x.png', image_bytes())}).status_code == 503
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'designer'
    assert client.post(ROOT + '/channel/resume').status_code == 403


@pytest.mark.parametrize('role', ['designer', 'operator', 'design_manager'])
def test_live_downgrade_denies_every_api_edit_entry_even_own_history(files_env, role, monkeypatch):
    from app.modules.api_image_edits import conversation_router

    client, factory, _, identity = files_env
    monkeypatch.setattr(conversation_router, 'session_factory', lambda: factory)
    task_id, payload = create(client, count=1)
    task = f'{ROOT}/tasks/{task_id}'
    item_id = client.get(task).json()['items'][0]['id']
    item = f'{task}/items/{item_id}'
    file = f"{ROOT}/files/{payload['materialFileId']}"
    turn = f'{item}/conversation/turns/{uuid4()}'
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = role

    assert client.get('/api/v1/auth/me').json()['role'] == role
    for path in [ROOT + '/status', ROOT + '/tasks', ROOT + '/creators', task, task + '/deletion',
                 task + '/zip', file, file + '/content', file + '/content?variant=256',
                 file + '/content?download=true', item + '/conversation', item + '/conversation/events']:
        assert client.get(path).status_code == 403, path
    assert client.head(file + '/content').status_code == 403
    assert client.delete(file).status_code == 403
    assert client.delete(task).status_code == 403
    assert client.post(ROOT + '/files', files={'file': ('x.png', image_bytes())}).status_code == 403
    for path, data in [
        (ROOT + '/tasks', payload), (ROOT + '/channel/resume', None), (task + '/retry', None),
        (item + '/retry', None), (item + '/stop', None), (item + '/restore', {'version': 1}),
        (item + '/revise', {'baseVersion': 1, 'text': '修改'}),
        (item + '/conversation/turns', {'baseVersion': 1, 'text': '修改'}),
        (turn + '/stop', None), (turn + '/adopt', {'baseVersion': 1}),
    ]:
        assert client.post(path, json=data, headers={'Idempotency-Key': str(uuid4())}).status_code == 403, path
