"""Studio API tests use isolated SQL/storage; no model is invoked."""
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4
from zipfile import ZipFile
import pytest
from sqlalchemy import select, func
from app.overseas.tasks.models import Task
from app.overseas.execution.models import Job
from app.overseas.execution import claims
from app.overseas.studio.models import Turn, Picture, Conversation
from app.overseas.studio.execution import HANDLER
from test_overseas_tasks import overseas, create, payload, ROOT, HEADERS
from test_overseas_materials import materials, upload
from test_overseas_assignment import change_roles
from test_overseas_plans import post


@pytest.fixture
def studio(materials, monkeypatch):
    from app.overseas.materials import parsers
    monkeypatch.setattr(parsers, 'parse_document', lambda *_: 'source text')
    client, factory, actor, designer, store = materials
    material = upload(client).json()
    task = create(client, {**payload(designer), 'materialIds': [material['id']]}).json()
    change_roles(factory, actor, ('super_admin',))
    approved = post(client, task, '/requirements-review',
                    {'version': 1, 'decision': 'approve'}, 'approve')
    assert approved.status_code == 200, approved.text
    assert approved.json()['status'] == 'studio'
    return client, factory, actor, task, material, store


def send(client, task, key='send', **kwargs):
    return post(client, task, '/studio/turns', {'text': '设计产品', **kwargs}, key)


def finish(factory, turn, pictures=None):
    identity = UUID(turn['jobId'])
    token = claims.claim(factory, identity)
    with factory.begin() as session:
        session.get(Job, identity).process_exited = True
    assert claims.finish(factory, identity, token, 'succeeded',
        dict(sessionId='thread-1', reply='请确认设计方向', pictures=pictures or []), publish=HANDLER.publish)


def test_send_replay_concurrency_events_and_text_turn(studio):
    client, factory, actor, task, material, _ = studio
    first = send(client, task, attachmentIds=['task:' + material['id']])
    assert first.status_code == 200, first.text
    data = first.json()
    turn = data['turns'][0]
    assert turn['status'] == 'queued' and turn['attachments'][0]['source'] == 'task'
    assert turn['referencePictures'] == []
    assert send(client, task, attachmentIds=['task:' + material['id']]).json() == data
    assert send(client, task, text='different').status_code == 409
    assert send(client, task, key='parallel').status_code == 409
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 1
        frozen = session.scalar(select(Job)).payload
        assert frozen['inputs'][0]['checksum'] == material_checksum(factory, material)
    finish(factory, turn)
    view = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()
    assert view['turns'][0]['reply'] == '请确认设计方向' and view['activeTurnId'] is None
    second = send(client, task, key='second', text='继续')
    assert second.status_code == 200 and len(second.json()['turns']) == 2
    events = client.get(ROOT + '/tasks/' + task['id'] + '/studio/events').json()
    assert len(events['items']) >= 3 and isinstance(events['cursor'], int)
    assert client.get(ROOT + '/tasks/' + task['id'] + '/studio/events?after=' + str(events['cursor'])).json()['items'] == []


def material_checksum(factory, material):
    from app.overseas.materials.models import Material
    with factory() as session:
        return session.get(Material, UUID(material['id'])).checksum


def test_scope_cross_task_attachments_and_cancel(studio):
    client, factory, actor, task, material, _ = studio
    other = create(client, payload(UUID(task['designer']['id'])), 'other').json()
    with factory.begin() as session:
        row = session.get(Task, UUID(other['id']))
        row.status, row.requirements_approved = 'studio', True
    assert send(client, other, attachmentIds=['task:' + material['id']]).status_code == 404
    turn = send(client, task).json()['turns'][0]
    assert post(client, other, '/studio/turns/' + turn['id'] + '/cancel', {'version': 1}).status_code == 404
    assert post(client, task, '/studio/turns/' + turn['id'] + '/cancel', {'version': 99}).status_code == 409
    cancelled = post(client, task, '/studio/turns/' + turn['id'] + '/cancel', {'version': 1})
    assert cancelled.json()['turns'][0]['status'] == 'cancelled'
    change_roles(factory, actor, ('designer',))
    assert client.get(ROOT + '/tasks/' + task['id'] + '/studio').status_code == 403
    assert send(client, task, key='forbidden').status_code == 403


def test_upload_original_content_formats_and_permissions(studio, monkeypatch):
    from app.overseas.studio import files
    monkeypatch.setattr(files, "MAX_BYTES", 20 * 1024 * 1024)
    client, factory, actor, task, _, _ = studio
    path = ROOT + '/tasks/' + task['id'] + '/studio/files'
    response = client.post(path, files={'file': ('notes.txt', b'hello')}, headers=HEADERS)
    assert response.status_code == 200, response.text
    asset = response.json()
    assert asset['id'].startswith('upload:') and client.get(asset['url']).content == b'hello'
    sent = send(client, task, text='', attachmentIds=[asset['id']])
    assert sent.status_code == 200
    for name, data, status in [('old.doc', b'doc', 422), ('old.ppt', b'ppt', 422),
                               ('bad.png', b'bad', 422), ('bad.txt', b'\x00', 422),
                               ('huge.txt', b'x' * (20 * 1024 * 1024 + 1), 413)]:
        result = client.post(path, files={'file': (name, data)}, headers=HEADERS)
        assert result.status_code == status, result.text
    change_roles(factory, actor, ('designer',))
    assert client.get(asset['url']).status_code == 403


def output(store):
    from PIL import Image
    from types import SimpleNamespace
    buffer = BytesIO()
    Image.new('RGB', (32, 32), 'red').save(buffer, format='PNG')
    data = buffer.getvalue()
    identity = uuid4()
    row = dict(id=str(identity), name='result.png', bucket='test', object_key='picture/' + str(identity),
               content_type='image/png', size_bytes=len(data), checksum=sha256(data).hexdigest(),
               width=32, height=32)
    store.put(SimpleNamespace(**row), data)
    return row


def test_multi_picture_partial_archive_zip_and_explicit_complete(studio):
    client, factory, _, task, _, store = studio
    assert post(client, task, '/studio/complete', {}, 'premature').status_code == 409
    turn = send(client, task).json()['turns'][0]
    pictures = [output(store), output(store)]
    finish(factory, turn, pictures)
    ids = [p['id'] for p in pictures]
    usage = client.get(ROOT + '/management/usage?kind=studio').json()
    assert usage['generationImages'] == 2 and usage['jobs'] == 1
    jobs = client.get(ROOT + '/management/jobs?kind=studio').json()
    assert jobs['items'][0]['imageCount'] == 2
    assert post(client, task, '/studio/archive', {'pictureIds': ids, 'sku': 'foreign'}, 'bad').status_code == 422
    archived = post(client, task, '/studio/archive', {'pictureIds': ids[:1], 'sku': 'A'}, 'archive')
    assert archived.status_code == 200 and not archived.json()['completed']
    assert post(client, task, '/studio/archive', {'pictureIds': ids[:1], 'sku': 'B'}, 'conflict').status_code == 409
    assert post(client, task, '/studio/archive', {'pictureIds': ids, 'sku': 'A'}, 'archive2').status_code == 200
    archive = client.get(ROOT + '/archives').json()['items'][0]
    assert archive['pictureCount'] == 2
    zipped = client.get(ROOT + '/archives/' + archive['id'] + '/download')
    with ZipFile(BytesIO(zipped.content)) as data:
        assert len(data.namelist()) == 2
    second = send(client, task, key='second', referencePictureIds=ids).json()['turns'][-1]
    assert [p['id'] for p in second['referencePictures']] == ids
    assert all(p['turnId'] == turn['id'] for p in second['referencePictures'])
    refreshed = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()
    assert refreshed['turns'][-1]['referencePictures'] == second['referencePictures']
    for referenced in refreshed['turns'][-1]['referencePictures']:
        assert client.get(referenced['url']).status_code == 200
    assert post(client, task, '/studio/complete', {}, 'busy').status_code == 409
    finish(factory, second)
    completed = post(client, task, '/studio/complete', {}, 'complete')
    assert completed.status_code == 200 and completed.json()['completed']
    assert post(client, task, '/studio/complete', {}, 'complete').json() == completed.json()
    assert send(client, task, key='after').status_code == 409


def test_legacy_workflow_and_unapproved_cannot_send(studio):
    client, factory, _, task, _, _ = studio
    with factory.begin() as session:
        current = session.get(Task, UUID(task['id']))
        current.requirements_approved = False
    assert send(client, task).status_code == 409
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).workflow = 'legacy'
    assert client.get(ROOT + '/tasks/' + task['id'] + '/studio').status_code == 409


def test_upload_multipart_is_bounded_and_single_file(studio, monkeypatch):
    from app.overseas.studio import files
    monkeypatch.setattr(files, "MAX_BYTES", 20 * 1024 * 1024)
    client, _, _, task, _, _ = studio
    path = ROOT + '/tasks/' + task['id'] + '/studio/files'
    response = client.post(path, files=[
        ('file', ('one.txt', b'one')), ('file', ('two.txt', b'two'))], headers=HEADERS)
    assert response.status_code == 422
    boundary = 'studio-upload-boundary'
    prefix = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
              'filename="huge.txt"\r\nContent-Type: text/plain\r\n\r\n').encode()
    suffix = f'\r\n--{boundary}--\r\n'.encode()
    def chunks():
        yield prefix
        for _ in range(22):
            yield b'x' * (1024 * 1024)
        yield suffix
    streamed = client.post(path, content=chunks(), headers={
        **HEADERS, 'Content-Type': 'multipart/form-data; boundary=' + boundary})
    assert streamed.status_code == 413
    declared = client.post(path, content=b'', headers={**HEADERS,
        'Content-Type': 'multipart/form-data; boundary=' + boundary,
        'Content-Length': str(21 * 1024 * 1024)})
    assert declared.status_code == 413
    view = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()
    assert not any(asset['source'] == 'upload' for asset in view['materials'])
