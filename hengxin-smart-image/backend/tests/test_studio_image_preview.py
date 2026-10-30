"""Image-only inline delivery keeps authentication, bounded streaming and download defaults."""
from io import BytesIO
from hashlib import sha256
from uuid import UUID

import pytest
from PIL import Image
from app.overseas.materials.models import Material
from test_overseas_tasks import overseas, ROOT, HEADERS
from test_overseas_materials import materials, upload
from test_overseas_assignment import change_roles
from test_overseas_studio import studio, send, finish, output


def test_generated_picture_head_preflights_without_reading_and_enforces_access(studio, monkeypatch):
    client, factory, actor, task, _, store = studio
    turn = send(client, task).json()['turns'][0]
    picture = output(store)
    finish(factory, turn, [picture])
    url = ROOT + '/tasks/' + task['id'] + '/studio/pictures/' + picture['id'] + '/content'
    downloaded = client.get(url)
    assert downloaded.status_code == 200
    monkeypatch.setattr(store, 'open', lambda *_: pytest.fail('HEAD opened picture bytes'))
    response = client.head(url)
    assert response.status_code == 200 and response.content == b''
    for name in ('content-type', 'content-length', 'content-disposition', 'cache-control'):
        assert response.headers[name] == downloaded.headers[name]
    store.data.clear()
    assert client.head(url).status_code == 503
    change_roles(factory, actor, ('designer',))
    assert client.head(url).status_code == 403
    client.cookies.clear()
    assert client.head(url).status_code == 401


@pytest.mark.parametrize('source', ['studio', 'material'])
@pytest.mark.parametrize('extension,content_type,format', [
    ('png', 'image/png', 'PNG'), ('jpg', 'image/jpeg', 'JPEG'), ('webp', 'image/webp', 'WEBP')])
def test_image_preview_get_head_and_download(studio, monkeypatch, source, extension, content_type, format):
    client, factory, actor, task, material, store = studio
    buffer = BytesIO()
    Image.new('RGB', (32, 32), 'blue').save(buffer, format=format)
    data = buffer.getvalue()
    if source == 'studio':
        response = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
            files={'file': ('图片.' + extension, data)}, headers=HEADERS)
        assert response.status_code == 200, response.text
        url = response.json()['url']
    else:
        # Historical image materials are read through the same authorization path.
        with factory.begin() as session:
            row = session.get(Material, UUID(material['id']))
            row.content_type, row.name, row.size_bytes = content_type, '图片.' + extension, len(data)
            row.checksum = sha256(data).hexdigest()
            store.put(row, data)
        url = ROOT + '/materials/' + material['id'] + '/content'
    opened = []
    original = store.open
    def track(row):
        opened.append(row.object_key)
        return original(row)
    monkeypatch.setattr(store, 'open', track)
    head = client.head(url + '?preview=true')
    assert head.status_code == 200 and head.content == b'' and not opened
    assert head.headers['content-disposition'].startswith('inline')
    image = client.get(url + '?preview=true')
    assert image.status_code == 200 and image.content == data
    assert image.headers['content-type'] == content_type
    assert image.headers['content-disposition'] == head.headers['content-disposition']
    assert image.headers['x-content-type-options'] == 'nosniff'
    assert image.headers['cache-control'] == 'private, no-cache'
    assert image.headers['etag'] == '"' + sha256(data).hexdigest() + '"'
    assert image.headers['etag'] == head.headers['etag']
    assert set(image.headers['vary'].lower().replace(' ', '').split(',')) == {'cookie', 'authorization'}
    assert client.get(url).headers['content-disposition'].startswith('attachment')
    assert client.head(url).headers['content-disposition'].startswith('attachment')
    change_roles(factory, actor, ('designer',))
    assert client.get(url + '?preview=true').status_code == 403
    assert client.head(url + '?preview=true').status_code == 403
    client.cookies.clear()
    assert client.get(url + '?preview=true').status_code == 401


@pytest.mark.parametrize('source', ['studio', 'material'])
def test_document_preview_refused_without_opening_storage(studio, monkeypatch, source):
    client, _, _, task, material, store = studio
    url = ROOT + '/materials/' + material['id'] + '/content'
    if source == 'studio':
        response = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
            files={'file': ('notes.txt', b'hello')}, headers=HEADERS)
        url = response.json()['url']
    monkeypatch.setattr(store, 'stat', lambda *_: pytest.fail('document preview accessed storage'))
    monkeypatch.setattr(store, 'open', lambda *_: pytest.fail('document preview accessed storage'))
    for method in (client.head, client.get):
        assert method(url + '?preview=true').status_code == 422


@pytest.mark.parametrize('content_type', ['image/svg+xml', 'text/html', 'application/pdf', 'image/gif'])
def test_unlisted_types_cannot_be_previewed(studio, content_type):
    client, factory, _, _, material, _ = studio
    with factory.begin() as session:
        session.get(Material, UUID(material['id'])).content_type = content_type
    assert client.get(ROOT + '/materials/' + material['id'] + '/content?preview=true').status_code == 422


def test_missing_image_preview_storage_returns_service_error(studio):
    client, factory, _, _, material, store = studio
    with factory.begin() as session:
        session.get(Material, UUID(material['id'])).content_type = 'image/png'
    store.data.clear()
    url = ROOT + '/materials/' + material['id'] + '/content?preview=true'
    assert client.head(url).status_code == 503
    assert client.get(url).status_code == 503
