import asyncio

import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile

from app.main import app
from app.modules.auth.dependencies import get_identity_id
from app.modules.files.multipart import MAX_BODY_BYTES, parse_upload
from files_helpers import files_env, image_bytes


def test_anonymous_and_declared_oversize_never_spool(files_env, monkeypatch):
    client, _, _, _ = files_env
    written = []
    original = UploadFile.write

    async def record(self, data):
        written.append(len(data))
        await original(self, data)

    monkeypatch.setattr(UploadFile, 'write', record)
    data = b'x' * (12 * 1024 * 1024)
    assert client.post('/api/v1/files', files={'file': ('x.png', data)}).status_code == 413
    assert not written
    app.dependency_overrides.pop(get_identity_id)
    assert client.post('/api/v1/files', files={'file': ('x.png', data)}).status_code == 401
    assert not written


@pytest.mark.parametrize('declared', [None, b'10'])
def test_chunked_or_false_length_stops_early_and_closes_spool(monkeypatch, declared):
    import starlette.formparsers as parser
    opened = []
    original = parser.SpooledTemporaryFile

    def spool(*args, **kwargs):
        value = original(*args, **kwargs)
        opened.append(value)
        return value

    monkeypatch.setattr(parser, 'SpooledTemporaryFile', spool)
    received = 0
    head = b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="x.png"\r\n\r\n'

    async def receive():
        nonlocal received
        received += 1
        # Represent an unbounded sender without allocating its whole payload.
        return {'type': 'http.request', 'body': head if received == 1 else b'x' * 65536,
                'more_body': True}

    headers = [(b'content-type', b'multipart/form-data; boundary=boundary')]
    if declared is not None:
        headers.append((b'content-length', declared))
    request = Request({'type': 'http', 'headers': headers}, receive)
    with pytest.raises(HTTPException) as error:
        asyncio.run(parse_upload(request))
    assert error.value.status_code == 413
    assert received <= MAX_BODY_BYTES // 65536 + 2
    assert opened and all(value.closed for value in opened)


def test_multipart_contract_single_file_only(files_env):
    client, _, _, _ = files_env
    for files in [[('wrong', ('x.png', image_bytes()))],
                  [('file', ('x.png', image_bytes())), ('file', ('y.png', image_bytes()))]]:
        assert client.post('/api/v1/files', files=files).status_code == 422
    assert client.post('/api/v1/files', files={'file': ('x.png', image_bytes())},
                       data={'ownerId': 'forged'}).status_code == 422
    assert client.post('/api/v1/files', content=b'bad multipart', headers={
        'Content-Type': 'multipart/form-data; boundary=boundary'}).status_code == 422
    schema = app.openapi()['paths']['/api/v1/files']['post']['requestBody']
    assert schema['content']['multipart/form-data']['schema']['required'] == ['file']
