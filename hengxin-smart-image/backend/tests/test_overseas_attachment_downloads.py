"""Download contracts cover both original-file entry points, never generated pictures."""
from io import BytesIO
from uuid import UUID
import asyncio
import pytest
from sqlalchemy import select
from app.overseas.materials.models import Material, ParseVersion
from app.overseas.tasks.models import Task
from test_overseas_tasks import overseas, create, payload, ROOT, HEADERS
from test_overseas_materials import materials, upload
from test_overseas_assignment import change_roles
from test_overseas_studio import studio, send, finish, output
from test_overseas_plans import post


@pytest.mark.parametrize('source', ['material', 'studio'])
def test_head_does_not_open_and_get_streams_bounded_chunks(studio, monkeypatch, source):
    client, factory, actor, task, material, store = studio
    data = b'original' * 20000
    if source == 'material':
        change_roles(factory, actor, ('super_admin',))
        item = upload(client, data, '很长的原件名称.pdf').json()
        url = ROOT + '/materials/' + item['id'] + '/content'
    else:
        item = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
            files={'file': ('long-file.txt', data)}, headers=HEADERS).json()
        url = item['url']
    opened = []
    class Tracked(BytesIO):
        released = False
        def read(self, size=-1):
            assert 0 < size <= 64 * 1024, 'download must not buffer entire original'
            return super().read(size)
        def stream(self, size):
            while chunk := self.read(size):
                yield chunk
        def release_conn(self):
            self.released = True
    def open_stream(row):
        stream = Tracked(store.data[row.object_key])
        opened.append(stream)
        return stream
    monkeypatch.setattr(store, 'open', open_stream)
    head = client.head(url)
    assert head.status_code == 200 and head.content == b'' and not opened
    assert int(head.headers['content-length']) == len(data)
    assert head.headers['content-disposition'].startswith('attachment')
    response = client.get(url)
    assert response.content == data and response.headers['content-disposition'] == head.headers['content-disposition']
    assert opened[0].closed and opened[0].released
    change_roles(factory, actor, ('designer',))
    assert client.head(url).status_code == 403
    assert client.get(url).status_code == 403
    client.cookies.clear()
    assert client.head(url).status_code == 401
    assert client.get(url).status_code == 401


@pytest.mark.parametrize('source', ['material', 'studio'])
def test_missing_storage_fails_preflight_and_get(studio, source):
    client, _, _, task, material, store = studio
    url = ROOT + '/materials/' + material['id'] + '/content'
    if source == 'studio':
        result = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
            files={'file': ('test.txt', b'hello')}, headers=HEADERS).json()
        url = result['url']
    store.data.clear()
    assert client.head(url).status_code == 503
    response = client.get(url)
    assert response.status_code == 503 and '原件' in response.text


def test_generated_picture_stays_inline(studio):
    client, factory, _, task, _, store = studio
    turn = send(client, task).json()['turns'][0]
    picture = output(store)
    finish(factory, turn, [picture])
    url = ROOT + '/tasks/' + task['id'] + '/studio/pictures/' + picture['id'] + '/content'
    response = client.get(url)
    assert response.status_code == 200 and response.headers['content-disposition'].startswith('inline')


@pytest.mark.parametrize('failure', ['checksum', 'missing', 'unsupported'])
def test_legacy_on_demand_rejects_invalid_original_without_jobs(materials, failure):
    from app.overseas.execution.models import Job
    client, factory, actor, designer, store = materials
    data = upload(client, b'opaque', 'test.doc' if failure == 'unsupported' else 'test.csv').json()
    task = create(client, {**payload(designer), 'materialIds': [data['id']]}).json()
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).workflow = 'legacy'
        assert session.scalar(select(ParseVersion)) is None
        row = session.get(Material, UUID(data['id']))
        if failure == 'checksum':
            store.data[row.object_key] = b'broken'
        elif failure == 'missing':
            store.data.clear()
    change_roles(factory, actor, ('super_admin',))
    result = post(client, task, '/requirements-review', {'version': 1, 'decision': 'approve'})
    assert result.status_code == (422 if failure == 'unsupported' else 503), result.text
    with factory() as session:
        assert session.scalar(select(Job)) is None
        assert session.get(Task, UUID(task['id'])).status == 'pending_review'


@pytest.mark.parametrize('failure_at', ['http.response.start', 'http.response.body'])
def test_stream_disconnect_releases_connection(studio, failure_at):
    from app.modules.files.streaming import OwnedStreamResponse
    class Stream:
        closed = released = False
        def stream(self, size):
            yield b'original'
        def close(self):
            self.closed = True
        def release_conn(self):
            self.released = True
    stream = Stream()
    response = OwnedStreamResponse(stream)
    async def send_message(message):
        if message['type'] == failure_at:
            raise OSError('disconnected')
    async def receive():
        return {'type': 'http.disconnect'}
    with pytest.raises(Exception):
        asyncio.run(response({'type': 'http', 'asgi': {'spec_version': '2.4'}}, receive, send_message))
    assert stream.closed and stream.released


@pytest.mark.parametrize('source', ['material', 'studio'])
def test_preflight_releases_database_before_storage(studio, monkeypatch, source):
    from app.overseas.auth.models import Member
    from app.overseas.materials import files as material_files
    from app.overseas.studio import files as studio_files
    client, factory, actor, task, material, store = studio
    identity = UUID(material['id'])
    if source == 'studio':
        asset = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
            files={'file': ('test.txt', b'hello')}, headers=HEADERS).json()
        identity = UUID(asset['id'].split(':')[1])
    original_stat = store.stat
    with factory() as session:
        def stat(row):
            assert not session.in_transaction()
            return original_stat(row)
        monkeypatch.setattr(store, 'stat', stat)
        member = session.get(Member, actor)
        if source == 'material':
            response = material_files.content(session, store, member, identity, head=True)
        else:
            response = studio_files.content(session, store, member, UUID(task['id']), identity, head=True)
        assert response.status_code == 200 and response.body == b''


def test_legacy_failed_parse_retries_internally_and_keeps_history(materials, monkeypatch):
    from app.overseas.materials import parsers
    from app.overseas.execution.models import Job
    client, factory, actor, designer, store = materials
    calls = []
    def parse(data, name):
        calls.append((data, name))
        return 'complete legacy text'
    monkeypatch.setattr(parsers, 'parse_document', parse)
    data = upload(client).json()
    assert calls == []
    task = create(client, {**payload(designer), 'materialIds': [data['id']]}).json()
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).workflow = 'legacy'
        row = session.get(Material, UUID(data['id']))
        row.version = 1
        session.add(ParseVersion(material_id=row.id, version=1, status='failed',
            parser_version='old', text='', error='previous failure'))
    change_roles(factory, actor, ('super_admin',))
    result = post(client, task, '/requirements-review', {'version': 1, 'decision': 'approve'})
    assert result.status_code == 200, result.text
    assert len(calls) == 1 and calls[0][0] == b'name,value\nitem,42\n'
    with factory() as session:
        history = list(session.scalars(select(ParseVersion).order_by(ParseVersion.version)))
        assert [row.status for row in history] == ['failed', 'ready']
        assert session.scalar(select(Job)).payload['materials'][0]['text'] == 'complete legacy text'
