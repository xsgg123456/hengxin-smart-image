import hashlib
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.resource_models import FileRecord, UserRecord
from files_helpers import files_env, image_bytes


def upload(client, data=None, name='素材.png', mime='image/png'):
    return client.post('/api/v1/files', files={'file': (name, image_bytes() if data is None else data, mime)})


@pytest.mark.parametrize('kind,mime', [('PNG', 'image/png'), ('JPEG', 'image/jpeg'), ('WEBP', 'image/webp')])
def test_original_bytes_metadata_and_private_download(files_env, kind, mime):
    client, factory, store, identity = files_env
    data = image_bytes(kind)
    response = upload(client, data, mime=mime)
    assert response.status_code == 200, response.text
    picture = response.json()
    assert set(picture) == {'name', 'url', 'fileId'}
    assert picture['url'] == f"/api/v1/files/{picture['fileId']}/content"
    assert client.get('/api/v1/files/' + picture['fileId']).json() == picture
    for suffix in ['', '?download=true']:
        result = client.get(picture['url'] + suffix)
        assert result.status_code == 200 and result.content == data
        assert result.headers['content-type'] == mime
        assert result.headers['cache-control'] == 'private, no-store'
        assert result.headers['content-disposition'].startswith('attachment' if suffix else 'inline')
    assert all(stream.closed and stream.released for stream in store.streams)
    with factory() as session:
        record = session.get(FileRecord, UUID(picture['fileId']))
        assert record.owner_id == identity[0]
        assert (record.width, record.height, record.size_bytes) == (8, 6, len(data))
        assert record.checksum == hashlib.sha256(data).hexdigest()
        assert record.status == 'ready'


@pytest.mark.parametrize('role', ['super_admin', 'design_manager', 'designer', 'operator'])
def test_all_roles_cross_owner_and_recheck_disabled(files_env, role):
    client, factory, _, identity = files_env
    picture = upload(client).json()
    with factory.begin() as session:
        other = UserRecord(id=uuid4(), name='另一成员', role=role, status='active', identity_source='development')
        session.add(other)
        identity[0] = other.id
    assert client.get(picture['url']).status_code == 200
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).status = 'disabled'
    assert client.get(picture['url']).status_code == 403
    assert client.get('/api/v1/files/' + picture['fileId']).status_code == 403
    assert upload(client).status_code == 403


@pytest.mark.parametrize('data,mime,code', [
    (b'', 'image/png', 422), (b'not image', 'image/png', 422),
    (b'a' * (10 * 1024 * 1024 + 1), 'image/png', 413),
    (image_bytes(), 'image/jpeg', 422),
    (image_bytes('GIF'), 'image/gif', 422),
    (image_bytes('JPEG')[:100], 'image/jpeg', 422),
    (image_bytes()[:-20], 'image/png', 422),
], ids=['empty', 'invalid', 'oversize', 'mismatch', 'gif', 'truncated-jpeg', 'truncated-png'])
def test_invalid_uploads_create_no_record(files_env, data, mime, code):
    client, factory, store, _ = files_env
    assert upload(client, data, mime=mime).status_code == code
    with factory() as session:
        assert session.scalars(select(FileRecord)).all() == []
    assert not store.objects


def test_bomb_and_exact_size_boundary(files_env, monkeypatch):
    client, _, _, _ = files_env
    with monkeypatch.context() as context:
        context.setattr('PIL.Image.MAX_IMAGE_PIXELS', 10)
        assert upload(client).status_code == 422
    data = image_bytes()
    assert upload(client, data + b'\0' * (10 * 1024 * 1024 - len(data))).status_code == 200


@pytest.mark.parametrize('fail_remove', [False, True])
def test_store_failure_never_exposes_staged_file_and_retry_succeeds(files_env, fail_remove):
    client, factory, store, _ = files_env
    store.fail_put, store.fail_remove = True, fail_remove
    assert upload(client).status_code == 503
    with factory() as session:
        failed = session.scalar(select(FileRecord))
        assert failed.status == 'failed'
        file_id = str(failed.id)
    assert client.get('/api/v1/files/' + file_id).status_code == 404
    assert client.get('/api/v1/files/' + file_id + '/content').status_code == 404
    store.fail_put = False
    assert upload(client).status_code == 200


def test_filename_safety_missing_and_storage_unavailable(files_env):
    client, _, store, _ = files_env
    picture = upload(client, name='../../测试<script>.exe').json()
    assert picture['name'] == '测试_script_.png'
    assert client.get('/api/v1/files/' + str(uuid4())).status_code == 404
    store.fail_open = True
    response = client.get(picture['url'])
    assert response.status_code == 503
    assert 'injected' not in response.text


def test_distinct_uploads_never_overwrite(files_env):
    client, _, store, _ = files_env
    first, second = upload(client).json(), upload(client).json()
    assert first['fileId'] != second['fileId'] and len(store.objects) == 2
