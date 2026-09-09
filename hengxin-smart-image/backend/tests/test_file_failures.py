from io import BytesIO
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from starlette.datastructures import Headers

from app.modules.files.service import save_upload
from app.modules.files.validation import validate_image
from app.modules.files.streaming import OwnedStreamResponse
from app.resource_models import FileRecord, UserRecord
from app.storage.minio_store import MinioStore
from files_helpers import ObjectStream, files_env, image_bytes


def test_database_finalize_failure_keeps_unpublished_staging(files_env, monkeypatch):
    client, factory, store, identity = files_env
    image = validate_image(UploadFile(BytesIO(image_bytes()), filename='x.png',
                                      headers=Headers({'content-type': 'image/png'})))
    with factory() as session:
        user = session.get(UserRecord, identity[0])
        real_commit, calls = session.commit, []

        def commit():
            calls.append(1)
            if len(calls) == 2:
                raise OSError('commit interrupted')
            real_commit()

        monkeypatch.setattr(session, 'commit', commit)
        with pytest.raises(HTTPException) as error:
            save_upload(session, store, user, image)
        assert error.value.status_code == 503
    with factory() as session:
        record = session.scalar(select(FileRecord))
        assert record.status == 'staging'
        assert record.object_key in store.objects
        assert client.get(f'/api/v1/files/{record.id}/content').status_code == 404


def test_storage_public_policy_rejected():
    store = object.__new__(MinioStore)
    store.client = SimpleNamespace(bucket_exists=lambda _: True,
                                   get_bucket_policy=lambda _: '{"Statement":[]}')
    with pytest.raises(RuntimeError, match='anonymous'):
        store.ensure_private('test')


@pytest.mark.parametrize('fail_at', [1, 2])
def test_disconnect_always_closes_storage_response(fail_at):
    stream = ObjectStream(b'original bytes')
    response = OwnedStreamResponse(stream)
    calls = []

    async def send(message):
        calls.append(message)
        if len(calls) == fail_at:
            raise OSError('client disconnected')

    async def receive():
        return {'type': 'http.disconnect'}

    from starlette.requests import ClientDisconnect
    with pytest.raises(ClientDisconnect):
        asyncio.run(response({'type': 'http', 'asgi': {'spec_version': '2.4'}}, receive, send))
    assert stream.closed and stream.released
