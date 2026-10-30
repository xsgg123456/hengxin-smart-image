"""HTTP cache revalidation always traverses real isolated auth/record/storage checks."""
from hashlib import sha256
from io import BytesIO
from uuid import UUID
import pytest
from PIL import Image
from app.overseas.archives.models import ArchiveAsset
from app.overseas.materials.models import Material
from app.overseas.studio.models import Picture, Upload
from app.overseas.studio.models import Turn
from app.overseas.execution.models import Job
from test_overseas_tasks import overseas, ROOT, HEADERS
from test_overseas_materials import materials, upload
from test_overseas_assignment import change_roles
from test_overseas_studio import studio, send, finish, output
from test_overseas_plans import post
from studio_sessions_helpers import base, channel, mutate, selected


def image_source(studio, source):
    client, factory, _, task, _, store = studio
    if source in ('picture', 'archive'):
        turn = send(client, task).json()['turns'][0]
        row = output(store)
        finish(factory, turn, [row])
        original = store.data[row['object_key']]
        if source == 'picture':
            return (ROOT + '/tasks/' + task['id'] + '/studio/pictures/' + row['id'] + '/content',
                    original, Picture, UUID(row['id']))
        result = post(client, task, '/studio/archive', {'pictureIds': [row['id']], 'sku': 'A'}, 'archive')
        assert result.status_code == 200, result.text
        archive = client.get(ROOT + '/archives').json()['items'][0]
        asset = client.get(ROOT + '/archives/' + archive['id']).json()['pictures'][0]
        return asset['url'], original, ArchiveAsset, UUID(asset['id'])
    buffer = BytesIO()
    Image.new('RGB', (1200, 600), '#8a2244').save(buffer, format='PNG')
    original = buffer.getvalue()
    if source == 'material':
        result = upload(client, original, 'original.png')
        assert result.status_code == 201, result.text
        asset = result.json()
        assert asset['contentType'] == 'image/png'
        return ROOT + '/materials/' + asset['id'] + '/content', original, Material, UUID(asset['id'])
    result = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
        files={'file': ('original.png', original)}, headers=HEADERS)
    assert result.status_code == 200, result.text
    asset = result.json()
    return asset['url'], original, Upload, UUID(asset['id'].split(':')[1])


@pytest.mark.parametrize('source', ['picture', 'upload', 'material', 'archive'])
def test_original_head_conditional_and_independent_thumbnail(studio, monkeypatch, source):
    client, _, _, _, _, store = studio
    url, original, _, _ = image_source(studio, source)
    first = client.get(url)
    assert first.status_code == 200 and first.content == original
    assert first.headers['etag'] == '"' + sha256(original).hexdigest() + '"'
    assert first.headers['cache-control'] == 'private, no-cache'
    assert set(first.headers['vary'].lower().replace(' ', '').split(',')) == {'cookie', 'authorization'}
    head = client.head(url)
    assert head.status_code == 200 and head.content == b''
    assert int(head.headers['content-length']) == len(original)
    thumbnail = client.get(url, params={'thumbnail': 'true'})
    assert thumbnail.status_code == 200, thumbnail.text
    assert thumbnail.headers['etag'] != first.headers['etag']
    assert thumbnail.headers['content-type'] == 'image/webp'
    with Image.open(BytesIO(thumbnail.content)) as image:
        assert max(image.size) <= 384
    assert client.get(url, params={'preview': 'true'}).content == original
    assert client.head(url, params={'thumbnail': 'true'}).headers['etag'] == thumbnail.headers['etag']
    original_open = store.open
    calls = []
    def tracked(row):
        calls.append(row.object_key)
        return original_open(row)
    monkeypatch.setattr(store, 'open', tracked)
    for method in ('get', 'head'):
        for validator in (first.headers['etag'], 'W/' + first.headers['etag'], '*', '"old", ' + first.headers['etag']):
            unchanged = getattr(client, method)(url, headers={'If-None-Match': validator})
            assert unchanged.status_code == 304 and unchanged.content == b''
            assert 'content-length' not in unchanged.headers
        thumb = getattr(client, method)(url, params={'thumbnail': 'true'},
            headers={'If-None-Match': thumbnail.headers['etag']})
        assert thumb.status_code == 304 and thumb.content == b''
    assert not calls, 'revalidation and cached derivatives must not download the original'
    assert client.get(url, headers={'If-None-Match': thumbnail.headers['etag']}).content == original
    assert len(calls) == 1


@pytest.mark.parametrize('source', ['picture', 'upload', 'material', 'archive'])
@pytest.mark.parametrize('failure', ['revoke', 'logout', 'record', 'object'])
def test_matching_validators_cannot_bypass_access_or_existence(studio, source, failure):
    client, factory, actor, _, _, store = studio
    url, _, model, identity = image_source(studio, source)
    original = client.get(url)
    thumbnail = client.get(url, params={'thumbnail': 'true'})
    if failure == 'revoke':
        change_roles(factory, actor, ('designer',))
        expected = 403
    elif failure == 'logout':
        client.cookies.clear()
        expected = 401
    elif failure == 'record':
        with factory.begin() as session:
            session.delete(session.get(model, identity))
        expected = 404
    else:
        store.data.clear()
        expected = 503
    for method in ('get', 'head'):
        for response, params in ((original, {}), (thumbnail, {'thumbnail': 'true'})):
            denied = getattr(client, method)(url, params=params, headers={'If-None-Match': response.headers['etag']})
            assert denied.status_code == expected, denied.text


def test_changed_checksum_replaces_validator_and_damaged_original_never_cached(studio):
    client, factory, _, _, _, store = studio
    url, original, model, identity = image_source(studio, 'upload')
    previous = client.get(url)
    changed = BytesIO()
    Image.new('RGB', (48, 32), 'blue').save(changed, format='PNG')
    new_bytes = changed.getvalue()
    with factory.begin() as session:
        row = session.get(model, identity)
        row.size_bytes, row.checksum = len(new_bytes), sha256(new_bytes).hexdigest()
        store.put(row, new_bytes)
    result = client.get(url, headers={'If-None-Match': previous.headers['etag']})
    assert result.status_code == 200 and result.content == new_bytes != original
    assert result.headers['etag'] != previous.headers['etag']
    with factory() as session:
        row = session.get(model, identity)
        store.data[row.object_key] = b'x' * len(new_bytes)
    assert client.get(url).status_code == 503
    assert client.get(url, params={'thumbnail': 'true'}).status_code == 503


def test_damaged_material_image_stays_private_download(studio):
    client = studio[0]
    item = upload(client, b'not a png', 'broken.png').json()
    assert item['contentType'] == 'application/octet-stream'
    url = ROOT + '/materials/' + item['id'] + '/content'
    response = client.get(url)
    assert response.content == b'not a png' and 'no-store' in response.headers['cache-control']
    assert client.get(url, params={'thumbnail': 'true'}).status_code == 422


@pytest.mark.parametrize('source', ['picture', 'upload', 'material', 'archive'])
def test_accepted_task_deletion_refuses_original_and_thumbnail_but_preserves_archive(studio, source):
    client, factory, _, task, _, _ = studio
    url, _, model, identity = image_source(studio, source)
    if source == 'material':
        with factory.begin() as session:
            session.get(model, identity).task_id = UUID(task['id'])
    responses = [(params, client.get(url, params=params)) for params in ({}, {'thumbnail': 'true'})]
    current = client.get(ROOT + '/tasks/' + task['id']).json()
    deleted = client.request('DELETE', ROOT + '/tasks/' + task['id'],
        json={'version': current['version']}, headers=HEADERS)
    assert deleted.status_code == 200, deleted.text
    for method in ('get', 'head'):
        for params, previous in responses:
            response = getattr(client, method)(url, params=params, headers={'If-None-Match': previous.headers['etag']})
            assert response.status_code == (304 if source == 'archive' else 404)


@pytest.mark.parametrize('source', ['picture', 'upload'])
def test_accepted_conversation_deletion_invalidates_private_images_before_cleanup(studio, source):
    client, factory, _, task, _, store = studio
    url, _, model, identity = image_source(studio, source)
    if source == 'upload':
        owner = channel(client, task)
        with factory.begin() as session:
            session.get(model, identity).conversation_id = UUID(owner)
    else:
        owner = client.get(base(task)).json()['conversationId']
    responses = [(params, client.get(url, params=params)) for params in ({}, {'thumbnail': 'true'})]
    current = next(row for row in selected(client, task, owner)['conversations'] if row['id'] == owner)
    assert mutate(client, task, owner, 'DELETE', {'version': current['version']}).status_code == 200
    assert store.data, 'this exercises accepted deletion before asynchronous erasure'
    for method in ('get', 'head'):
        for params, previous in responses:
            assert getattr(client, method)(url, params=params,
                headers={'If-None-Match': previous.headers['etag']}).status_code == 404


@pytest.mark.parametrize('source', ['material', 'upload', 'archive'])
def test_other_session_deletion_does_not_hide_shared_materials_or_archives(studio, source):
    client, factory, _, task, _, _ = studio
    url, _, model, identity = image_source(studio, source)
    if source == 'material':
        with factory.begin() as session:
            session.get(model, identity).task_id = UUID(task['id'])
    previous = client.get(url)
    other = channel(client, task)
    assert mutate(client, task, other, 'DELETE', {'version': 1}).status_code == 200
    assert client.get(url, headers={'If-None-Match': previous.headers['etag']}).status_code == 304


@pytest.mark.parametrize('detached', [False, True])
@pytest.mark.parametrize('reference', ['reference_ids', 'frozen_input'])
def test_legacy_shared_picture_stays_valid_until_last_consumer_deleted(studio, detached, reference):
    client, factory, _, task, _, _ = studio
    url, _, model, identity = image_source(studio, 'picture')
    owner = client.get(base(task)).json()['conversationId']
    other = channel(client, task, 'consumer')
    consumer = send(client, task, key='consumer-turn', conversationId=other).json()['turns'][0]
    finish(factory, consumer)
    # Preserve the supported pre-isolation references, including post-cleanup detachment.
    with factory.begin() as session:
        row = session.get(model, identity)
        turn = session.get(Turn, UUID(consumer['id']))
        if reference == 'reference_ids':
            turn.reference_ids = [str(identity)]
        else:
            job = session.get(Job, turn.job_id)
            job.payload = {**job.payload, 'inputs': [{'bucket': row.bucket, 'object_key': row.object_key}]}
        if detached:
            row.origin_turn_id, row.turn_id = row.turn_id, None
    previous = client.get(url)
    assert mutate(client, task, owner, 'DELETE', {'version': 2}).status_code == 200
    for method in ('get', 'head'):
        assert getattr(client, method)(url, headers={'If-None-Match': previous.headers['etag']}).status_code == 304
    assert mutate(client, task, other, 'DELETE', {'version': 2}, 'delete-consumer').status_code == 200
    for method in ('get', 'head'):
        assert getattr(client, method)(url, headers={'If-None-Match': previous.headers['etag']}).status_code == 404
