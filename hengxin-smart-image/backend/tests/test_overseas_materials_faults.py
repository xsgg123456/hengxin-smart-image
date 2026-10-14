from uuid import UUID
import pytest
from sqlalchemy import select
from app.core.idempotency import fingerprint_payload
from app.overseas.auth.models import Member
from app.overseas.materials import files, parsers
from app.overseas.materials.models import Material
from app.overseas.tasks.models import TaskRequest, Task
from app.overseas.tasks.schemas import CreateTask
from test_overseas_tasks import overseas, payload, create, counts, ROOT, HEADERS, add_member
from test_overseas_materials import materials, upload, submit
from test_overseas_assignment import change_roles


def test_phase19_hash_replays_without_new_field(materials):
    client, factory, _, designer, _ = materials
    body = payload(designer)
    data = create(client, body).json()
    old = CreateTask(**body).model_dump(mode='json', exclude={'materialIds'})
    with factory.begin() as session:
        session.scalar(select(TaskRequest)).body_hash = fingerprint_payload(old)
    assert create(client, body).status_code == 200
    assert counts(factory) == [1, 2, 1, 1, 1]


def test_ambiguous_ready_commit_preserves_original(materials, monkeypatch):
    _, factory, actor, _, store = materials
    monkeypatch.setattr(parsers, 'parse_document', lambda *_: 'text')
    with factory() as session:
        original = session.commit
        calls = 0
        def ambiguous():
            nonlocal calls
            calls += 1
            original()
            if calls == 2:
                raise RuntimeError('commit acknowledgement lost')
        monkeypatch.setattr(session, 'commit', ambiguous)
        with pytest.raises(Exception) as exc:
            files.save_upload(session, store, session.get(Member, actor), b'a,b', 'x.csv', 'competitor')
        assert exc.value.status_code == 503
    with factory() as session:
        record = session.scalar(select(Material))
        assert record.status == 'ready' and record.object_key in store.data


def test_ambiguous_tombstone_commit_never_deletes_storage(materials, monkeypatch):
    client, factory, actor, _, store = materials
    material_id = UUID(upload(client).json()['id'])
    with factory() as session:
        original = session.commit
        def ambiguous():
            original()
            raise RuntimeError('unknown commit')
        monkeypatch.setattr(session, 'commit', ambiguous)
        with pytest.raises(RuntimeError):
            files.delete(session, store, session.get(Member, actor), material_id)
    assert store.data
    assert client.get(ROOT + '/materials/' + str(material_id)).status_code == 404
    assert client.delete(ROOT + '/materials/' + str(material_id), headers=HEADERS).status_code == 204


def test_storage_failures_safe_and_not_visible(materials, monkeypatch):
    client, factory, _, _, store = materials
    def fail(*_):
        raise RuntimeError('secret endpoint')
    monkeypatch.setattr(store, 'put', fail)
    response = upload(client)
    assert response.status_code == 503 and 'secret endpoint' not in response.text
    with factory() as session:
        record = session.scalar(select(Material))
        assert record.status == 'failed'
        identifier = str(record.id)
    assert client.get(ROOT + '/materials/' + identifier).status_code == 404


def test_upload_revalidates_permission_after_staging(materials, monkeypatch):
    client, factory, actor, _, store = materials
    original = store.put
    def revoked(record, data):
        original(record, data)
        change_roles(factory, actor, ('designer',))
    monkeypatch.setattr(store, 'put', revoked)
    assert upload(client).status_code == 403
    with factory() as session:
        record = session.scalar(select(Material))
        assert record.status == 'staging' and record.version == 0
        assert record.object_key in store.data
    assert client.get(ROOT + '/materials/' + str(record.id)).status_code == 404


def test_content_storage_failure_and_size_mismatch(materials, monkeypatch):
    client, factory, _, _, store = materials
    data = upload(client).json()
    path = ROOT + '/materials/' + data['id']
    with factory() as session:
        key = session.get(Material, UUID(data['id'])).object_key
    store.data[key] = b'corrupted'
    assert client.get(path + '/content').status_code == 503
    assert client.head(path + '/content').status_code == 503
    def fail(*_):
        raise RuntimeError('private endpoint')
    monkeypatch.setattr(store, 'stat', fail)
    response = client.get(path + '/content')
    assert response.status_code == 503 and 'private endpoint' not in response.text
    assert client.get(path).json()['status'] == 'ready'


def test_manager_supplement_own_files_and_regular_operator_refused(materials):
    client, factory, actor, designer, _ = materials
    task = create(client, payload(designer)).json()
    stranger = add_member(factory, ('operator',))
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).created_by = stranger
    data = upload(client).json()
    assert submit(client, task['id'], [data['id']]).status_code == 403
    change_roles(factory, actor, ('operator_manager',))
    assert submit(client, task['id'], [data['id']]).status_code == 200


def test_two_kinds_submitted_and_pdf_download(materials, monkeypatch):
    client, factory, _, designer, _ = materials
    competitor = upload(client).json()
    monkeypatch.setattr(parsers, 'parse_document', lambda *_: '图需文字')
    requirement = upload(client, b'%PDF-test', 'test.pdf', 'requirement').json()
    path = ROOT + '/materials/' + requirement['id'] + '/content'
    assert client.get(path).headers['content-disposition'].startswith('attachment')
    assert client.get(path + '?download=true').headers['content-disposition'].startswith('attachment')
    response = create(client, {**payload(designer), 'materialIds': [competitor['id'], requirement['id']]})
    assert response.status_code == 201
    assert len(client.get(ROOT + '/tasks/' + response.json()['id'] + '/materials').json()) == 2


def test_supplement_rollback_preserves_created_and_unbound(materials, monkeypatch):
    from app.overseas.materials import service
    client, factory, _, designer, _ = materials
    task = create(client, payload(designer)).json()
    data = upload(client).json()
    def fail(*args):
        args[0].flush()
        raise RuntimeError('injected')
    monkeypatch.setattr(service, 'request_record', fail)
    with pytest.raises(RuntimeError):
        submit(client, task['id'], [data['id']])
    assert counts(factory) == [1, 2, 1, 1, 1]
    assert client.get(ROOT + '/tasks/' + task['id']).json()['status'] == 'created'
    assert client.get(ROOT + '/materials/' + data['id']).json()['taskId'] is None
