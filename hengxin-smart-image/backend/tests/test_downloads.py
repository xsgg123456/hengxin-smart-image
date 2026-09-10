import asyncio
import hashlib
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

import pytest

from app.modules.files.downloads import ZipStream
from app.modules.files.streaming import OwnedStreamResponse
from app.resource_models import UserRecord
from files_helpers import files_env, image_bytes
from test_files import upload


def test_zip_order_names_bytes_and_no_buffering(files_env):
    client, _, store, _ = files_env
    pictures = [upload(client, image_bytes(kind), name='same.png', mime=mime).json()
                for kind, mime in [('JPEG', 'image/jpeg'), ('PNG', 'image/png'), ('WEBP', 'image/webp')]]
    response = client.post('/api/v1/files/download-zip', json={
        'fileIds': [p['fileId'] for p in pictures], 'name': '../../CON.exe'})
    assert response.status_code == 200, response.text
    assert response.headers['content-type'] == 'application/zip'
    assert response.headers['cache-control'] == 'private, no-store'
    assert 'content-length' not in response.headers
    assert 'CON.zip' in response.headers['content-disposition']
    with ZipFile(BytesIO(response.content)) as archive:
        assert archive.namelist() == ['01-same.jpg', '02-same.png', '03-same.webp']
        for name, kind in zip(archive.namelist(), ['JPEG', 'PNG', 'WEBP']):
            assert archive.read(name) == image_bytes(kind)
    assert all(s.closed and s.released for s in store.streams)


@pytest.mark.parametrize('role', ['super_admin', 'design_manager', 'designer', 'operator'])
def test_zip_shared_permission_and_disabled_member(files_env, role):
    client, factory, _, identity = files_env
    picture = upload(client).json()
    with factory.begin() as session:
        user = UserRecord(id=uuid4(), name='下载者', role=role, status='active', identity_source='development')
        session.add(user)
        identity[0] = user.id
    body = {'fileIds': [picture['fileId']], 'name': '套图'}
    assert client.post('/api/v1/files/download-zip', json=body).status_code == 200
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).status = 'disabled'
    assert client.post('/api/v1/files/download-zip', json=body).status_code == 403
    identity[0] = uuid4()
    assert client.post('/api/v1/files/download-zip', json=body).status_code == 401


@pytest.mark.parametrize('ids', [[], ['bad'], [str(uuid4())] * 21])
def test_zip_invalid_ids(files_env, ids):
    client, _, store, _ = files_env
    assert client.post('/api/v1/files/download-zip', json={'fileIds': ids, 'name': '套图'}).status_code == 422
    assert not store.streams


def test_zip_missing_object_and_partial_open_release(files_env):
    client, _, store, _ = files_env
    pictures = [upload(client).json(), upload(client).json()]
    body = {'fileIds': [p['fileId'] for p in pictures], 'name': '套图'}
    assert client.post('/api/v1/files/download-zip', json={**body, 'fileIds': [str(uuid4())]}).status_code == 404
    store.objects.pop(f"originals/{pictures[1]['fileId']}")
    response = client.post('/api/v1/files/download-zip', json=body)
    assert response.status_code == 503
    assert all(s.closed and s.released for s in store.streams)


class LargeSource:
    def __init__(self, count=128):
        self.count, self.reads = count, 0
        self.closed = self.released = False

    def stream(self, size):
        assert size == 65536
        for _ in range(self.count):
            self.reads += 1
            yield b'a' * size

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


def large_zip(count=128, checksum=None):
    source = LargeSource(count)
    digest = hashlib.sha256()
    for _ in range(count):
        digest.update(b'a' * 65536)
    record = SimpleNamespace(name='../image.exe', content_type='image/png',
                             size_bytes=count * 65536, checksum=checksum or digest.hexdigest())
    return ZipStream([record], SimpleNamespace(open=lambda _: source)), source


def test_large_zip_is_incremental_and_checksum_checked():
    stream, source = large_zip()
    iterator = stream.stream(65536)
    assert next(iterator).startswith(b'PK') and source.reads == 0
    largest = 0
    for chunk in iterator:
        largest = max(largest, len(chunk))
    stream.close()
    assert largest <= 65536 and source.reads == 128
    assert source.closed and source.released
    stream, source = large_zip(1, '0' * 64)
    with pytest.raises(OSError, match='integrity'):
        list(stream.stream(65536))
    stream.close()
    assert source.closed and source.released


@pytest.mark.parametrize('fail_after', [0, 2])
def test_disconnect_before_and_during_iteration_closes_all(fail_after):
    stream, source = large_zip()
    response = OwnedStreamResponse(stream, media_type='application/zip')
    sent = 0

    async def send(message):
        nonlocal sent
        sent += 1
        if sent > fail_after:
            raise OSError('client disconnected')

    async def receive():
        return {'type': 'http.disconnect'}

    async def run():
        with pytest.raises(Exception):
            await response({'type': 'http', 'asgi': {'spec_version': '2.4'}}, receive, send)

    asyncio.run(run())
    assert source.closed and source.released
    assert source.reads < source.count
