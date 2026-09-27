import hashlib
import json
import random
from datetime import timedelta
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import delete

from app.models import utcnow
from app.modules.files.variant_worker import process_one
from app.modules.files.variants import ImageVariants, backfill
from app.resource_models import FileRecord, UserRecord
from files_helpers import files_env
from test_api_image_domain import enabled_api


def upload(env, domain='originals'):
    output = BytesIO()
    image = Image.frombytes('RGB', (1200, 900), random.Random(1).randbytes(1200 * 900 * 3))
    image.save(output, 'PNG')
    data = output.getvalue()
    path = '/api/v1/files' if domain == 'originals' else '/api/v1/api-image-edits/files'
    response = env[0].post(path, files={'file': ('sample.png', data, 'image/png')})
    assert response.status_code == 200, response.text
    picture = response.json()
    return picture, data


@pytest.mark.parametrize('domain', ['originals', 'api-image-edits'])
def test_private_display_smaller_original_intact_and_authorization_before_304(files_env, domain):
    client, factory, store, identity = files_env
    picture, original = upload(files_env, domain)
    path = picture['url'] + '?variant=256'
    pending = client.get(path)
    assert pending.content == original
    assert process_one(factory, store)
    small = client.get(path)
    assert small.status_code == 200 and len(small.content) < len(original) / 10
    assert small.headers['cache-control'] == 'private, no-cache'
    with Image.open(BytesIO(small.content)) as image:
        assert max(image.size) <= 256
    medium = client.get(picture['url'] + '?variant=1024')
    with Image.open(BytesIO(medium.content)) as image:
        assert max(image.size) <= 1024
    assert small.headers['etag'] != pending.headers['etag']
    tag = {'If-None-Match': small.headers['etag']}
    hit = client.get(path, headers=tag)
    assert hit.status_code == 304 and hit.content == b''
    assert client.head(path).headers['content-length'] == str(len(small.content))
    assert client.get(picture['url']).content == original
    assert client.get(path + '&download=true').content == original
    assert client.get(picture['url'] + '?variant=999').status_code == 422
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).status = 'disabled'
    denied = client.get(path, headers=tag)
    assert denied.status_code == 403 and denied.headers['cache-control'] == 'private, no-store'
    print('IMAGE_COMPARISON ' + json.dumps({'domain': domain, 'original': len(original),
        '256': len(small.content), '1024': len(medium.content), 'revalidated_body': len(hit.content)}))


def test_retry_after_put_failure_and_expired_claim_is_idempotent(files_env):
    _, factory, store, _ = files_env
    picture, original = upload(files_env)
    key = ('originals', UUID(picture['fileId']))
    store.fail_put = True
    assert process_one(factory, store)
    with factory.begin() as session:
        row = session.get(ImageVariants, key)
        assert not row.completed and not row.outputs and row.attempts == 1
        row.next_attempt = utcnow() - timedelta(seconds=1)
        row.token, row.lease_until = uuid4(), utcnow() - timedelta(seconds=1)
    store.fail_put = False
    assert process_one(factory, store)
    with factory() as session:
        assert session.get(ImageVariants, key).completed
    assert not process_one(factory, store)
    assert hashlib.sha256(store.objects[f'originals/{key[1]}']).digest() == hashlib.sha256(original).digest()


def test_legacy_backfill_is_bounded_and_deleted_source_never_delivered(files_env):
    client, factory, store, _ = files_env
    picture, _ = upload(files_env)
    with factory.begin() as session:
        session.execute(delete(ImageVariants))
    assert backfill(factory, 1) == 1
    assert backfill(factory, 1) == 0
    assert process_one(factory, store)
    path = picture['url'] + '?variant=256'
    tag = client.get(path).headers['etag']
    with factory.begin() as session:
        session.get(FileRecord, UUID(picture['fileId'])).deleted_at = utcnow()
    response = client.get(path, headers={'If-None-Match': tag})
    assert response.status_code == 404 and response.headers['cache-control'] == 'private, no-store'


def test_storage_failure_does_not_return_304(files_env):
    client, factory, store, _ = files_env
    picture, _ = upload(files_env)
    assert process_one(factory, store)
    path = picture['url'] + '?variant=256'
    tag = client.get(path).headers['etag']
    store.fail_open = True
    response = client.get(path, headers={'If-None-Match': tag})
    assert response.status_code == 503 and response.headers['cache-control'] == 'private, no-store'
