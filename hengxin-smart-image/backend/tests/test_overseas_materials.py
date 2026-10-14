from io import BytesIO
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from app.overseas.materials import parsers
from app.overseas.materials.models import Material, ParseVersion
from app.overseas.tasks.models import Task
from app.storage.minio_store import get_store
from test_overseas_tasks import overseas, setup, payload, create, add_member, counts, ROOT, HEADERS
from test_overseas_assignment import change_roles, assign


class Stream(BytesIO):
    def stream(self, size):
        while chunk := self.read(size):
            yield chunk

    def release_conn(self):
        pass


class MemoryStore:
    def __init__(self):
        self.data = {}
        self.buckets = {}
        self.fail_remove = False

    def put(self, record, data):
        self.data[record.object_key] = data
        self.buckets[record.object_key] = record.bucket

    def open(self, record):
        return Stream(self.data[record.object_key])

    def stat(self, record):
        return len(self.data[record.object_key])

    def keys(self, bucket, prefix):
        return [key for key in self.data if key.startswith(prefix) and self.buckets.get(key) == bucket]

    def remove(self, record):
        if self.fail_remove:
            raise RuntimeError('private storage path')
        self.data.pop(record.object_key, None)
        self.buckets.pop(record.object_key, None)


@pytest.fixture
def materials(overseas):
    client, factory, actor, designer = setup(overseas)
    store = MemoryStore()
    client.app.dependency_overrides[get_store] = lambda: store
    return client, factory, actor, designer, store


def upload(client, data=b'name,value\nitem,42\n', name='test.csv', kind='competitor'):
    return client.post(ROOT + '/materials?kind=' + kind,
                       files={'file': (name, data, 'application/octet-stream')}, headers=HEADERS)


def submit(client, task, ids, key='submit', version=1):
    return client.post(ROOT + '/tasks/' + task + '/materials',
                       json={'materialIds': ids, 'version': version},
                       headers={**HEADERS, 'Idempotency-Key': key})


def test_upload_content_and_versions(materials):
    client, factory, _, _, store = materials
    response = upload(client)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data['status'] == 'ready' and data['version'] == 1 and '42' in data['text']
    assert set(data) == {'id', 'kind', 'name', 'sizeBytes', 'contentType', 'status', 'taskId',
                         'version', 'parserVersion', 'text', 'error', 'createdAt', 'versions'}
    content = client.get(ROOT + '/materials/' + data['id'] + '/content')
    assert content.content == b'name,value\nitem,42\n'
    assert content.headers['content-disposition'].startswith('attachment')
    assert 'no-store' in content.headers['cache-control']
    assert content.headers['x-content-type-options'] == 'nosniff'
    retry = client.post(ROOT + '/materials/' + data['id'] + '/retry', headers=HEADERS)
    assert retry.status_code == 200 and len(retry.json()['versions']) == 2
    assert retry.json()['versions'][0] == data['versions'][0]


@pytest.mark.parametrize('data,name,kind,status', [
    (b'', 'test.csv', 'competitor', 422),
    (b'x' * (20 * 1024 * 1024 + 1), 'big.csv', 'competitor', 413),
], ids=['empty', 'oversize'])
def test_validation(materials, data, name, kind, status, monkeypatch):
    from app.overseas.materials import files
    monkeypatch.setattr(files, "MAX_BYTES", 20 * 1024 * 1024)
    monkeypatch.setattr(parsers, "MAX_DOCUMENT_BYTES", 20 * 1024 * 1024)
    client, factory, _, _, store = materials
    assert upload(client, data, name, kind).status_code == status
    assert not store.data
    with factory() as session:
        assert session.scalar(select(Material)) is None


def test_parse_failure_retains_original_and_retry(materials, monkeypatch):
    client, factory, _, designer, store = materials
    data = upload(client, b'%PDF-broken', 'test.pdf', 'requirement').json()
    assert data['status'] == 'failed' and data['error']
    assert client.get(ROOT + '/materials/' + data['id'] + '/content').content == b'%PDF-broken'
    monkeypatch.setattr(parsers, 'parse_document', lambda *_: '恢复的文字')
    retry = client.post(ROOT + '/materials/' + data['id'] + '/retry', headers=HEADERS).json()
    assert retry['status'] == 'ready' and retry['version'] == 2
    assert retry['versions'][0]['status'] == 'failed'


def test_atomic_create_and_bound_immutability(materials):
    client, factory, actor, designer, store = materials
    data = upload(client).json()
    body = {**payload(designer), 'materialIds': [data['id']]}
    first = create(client, body)
    assert first.status_code == 201, first.text
    task = first.json()
    assert task['status'] == 'pending_review' and 'task.materials.submit' not in task['capabilities']
    assert create(client, body).status_code == 200
    assert counts(factory) == [1, 2, 1, 1, 1]
    path = ROOT + '/materials/' + data['id']
    assert client.get(path).json()['taskId'] == task['id']
    assert client.get(ROOT + '/tasks/' + task['id'] + '/materials').json()[0]['id'] == data['id']
    assert client.post(path + '/retry', headers=HEADERS).status_code == 409
    assert client.delete(path, headers=HEADERS).status_code == 409
    assert create(client, body, 'other-task').status_code == 409
    assert counts(factory) == [1, 2, 1, 1, 1]


def test_supplement_version_idempotency_and_original_freeze(materials):
    client, factory, _, designer, _ = materials
    task = create(client, payload(designer)).json()
    data = upload(client).json()
    assert submit(client, task['id'], [data['id']], version=2).status_code == 409
    response = submit(client, task['id'], [data['id']])
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'pending_review' and response.json()['version'] == 2
    assert response.json()['events'][-1]['kind'] == 'task.materials_submitted'
    assert submit(client, task['id'], [data['id']]).status_code == 200
    assert submit(client, task['id'], [data['id']], key='different', version=2).status_code == 409
    assert counts(factory) == [1, 2, 2, 2, 2]


def test_ownership_revocation_and_unrecognized_ids(materials):
    client, factory, actor, designer, _ = materials
    data = upload(client).json()
    with factory.begin() as session:
        session.get(Material, UUID(data['id'])).owner_id = designer
    path = ROOT + '/materials/' + data['id']
    for suffix in ('', '/content'):
        assert client.get(path + suffix).status_code == 403
    assert client.post(path + '/retry', headers=HEADERS).status_code == 403
    assert client.delete(path, headers=HEADERS).status_code == 403
    assert create(client, {**payload(designer), 'materialIds': [data['id']]}).status_code == 403
    assert client.get(ROOT + '/materials/' + str(uuid4())).status_code == 404
    assert create(client, {**payload(designer), 'materialIds': [str(uuid4())]}).status_code == 404
    change_roles(factory, actor, ('designer',))
    assert upload(client).status_code == 403


def test_reassignment_revokes_previous_designer(materials):
    client, factory, actor, designer, _ = materials
    data = upload(client).json()
    task = create(client, {**payload(designer), 'materialIds': [data['id']]}).json()
    stranger = add_member(factory, ('operator',))
    with factory.begin() as session:
        record = session.get(Task, UUID(task['id']))
        record.created_by, record.designer_id = stranger, actor
    change_roles(factory, actor, ('designer',))
    path = ROOT + '/materials/' + data['id']
    assert client.get(path + '/content').status_code == 200
    change_roles(factory, actor, ('design_manager',))
    assert assign(client, task['id'], designer).status_code == 200
    change_roles(factory, actor, ('designer',))
    assert client.get(path).status_code == 403
    assert client.get(path + '/content').status_code == 403
    assert client.get(ROOT + '/tasks/' + task['id'] + '/materials').status_code == 403


def test_tombstone_delete_failure_retry_and_bind_rejection(materials):
    client, factory, _, designer, store = materials
    data = upload(client).json()
    path = ROOT + '/materials/' + data['id']
    store.fail_remove = True
    response = client.delete(path, headers=HEADERS)
    assert response.status_code == 503 and 'private storage path' not in response.text
    assert client.get(path).status_code == 404 and store.data
    assert create(client, {**payload(designer), 'materialIds': [data['id']]}).status_code == 404
    store.fail_remove = False
    assert client.delete(path, headers=HEADERS).status_code == 204
    assert not store.data


def test_binding_failure_rolls_back_material_task_event_and_outbox(materials, monkeypatch):
    from app.overseas.tasks import service
    client, factory, _, designer, _ = materials
    data = upload(client).json()
    def failure(*args):
        args[0].flush()
        raise RuntimeError('injected')
    monkeypatch.setattr(service, 'request_record', failure)
    with pytest.raises(RuntimeError, match='injected'):
        create(client, {**payload(designer), 'materialIds': [data['id']]})
    assert counts(factory) == [0] * 5
    assert client.get(ROOT + '/materials/' + data['id']).json()['taskId'] is None


def test_same_kind_duplicate_and_empty_materials_rejected(materials):
    client, factory, _, designer, _ = materials
    first, second = upload(client).json(), upload(client).json()
    for ids, code in (([], 422), ([first['id'], first['id']], 422),
                      ([first['id'], second['id']], 422), (None, 422)):
        assert create(client, {**payload(designer), 'materialIds': ids}).status_code == code
    assert counts(factory) == [0] * 5


def test_browser_write_protection_and_malformed_multipart(materials):
    client, _, _, _, _ = materials
    assert client.post(ROOT + '/materials?kind=competitor', files={'file': ('x.csv', b'x')}).status_code == 403
    response = client.post(ROOT + '/materials?kind=competitor', content=b'not multipart',
                           headers={**HEADERS, 'Content-Type': 'multipart/form-data; boundary=x'})
    assert response.status_code == 422


@pytest.mark.parametrize('name', ['brief.ppt', 'brief.pptx', 'brief.doc', 'reference.zip', 'notes', 'table.csv'])
def test_unparsed_original_can_submit_and_download(materials, name):
    client, factory, _, designer, store = materials
    original = b'opaque original file bytes'
    response = upload(client, original, name, 'requirement')
    assert response.status_code == 201, response.text
    material = response.json()
    if not name.endswith('.csv'):
        assert material['status'] == 'failed' and material['text'] == ''
    task = create(client, {**payload(designer), 'materialIds': [material['id']]} )
    assert task.status_code == 201, task.text
    assert task.json()['status'] == 'pending_review'
    content = client.get(ROOT + '/materials/' + material['id'] + '/content')
    assert content.content == original
    assert content.headers['content-disposition'].startswith('attachment')
    assert content.headers['x-content-type-options'] == 'nosniff'
