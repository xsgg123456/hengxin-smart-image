"""Real byte boundaries plus unchanged per-turn schema limits; isolated, no model call."""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.overseas.materials import parsers, files as materials
from app.overseas.studio import files as studio
from app.overseas.studio.schemas import Send
from app.overseas.upload_limits import MAX_UPLOAD_BYTES


def test_real_500mb_upload_boundaries():
    assert MAX_UPLOAD_BYTES == materials.MAX_BYTES == studio.MAX_BYTES == parsers.MAX_DOCUMENT_BYTES == 500_000_000
    data = b'%PDF-' + b'x' * (MAX_UPLOAD_BYTES - 5)
    assert parsers.validate_document(data, 'a.pdf', 'requirement')[1] == 'application/pdf'
    assert studio.validate(data, 'a.pdf')[1] == 'application/pdf'
    with pytest.raises(parsers.ParseError, match='原件已保存'):
        parsers.parse_document(data, 'a.pdf')
    del data
    data = b'x' * (MAX_UPLOAD_BYTES + 1)
    for validate, args in ((parsers.validate_document, ('a.pdf', 'requirement')), (studio.validate, ('a.pdf',))):
        with pytest.raises(HTTPException) as caught:
            validate(data, *args)
        assert caught.value.status_code == 413
        assert '500 MB' in caught.value.detail


def test_independent_100_item_limits():
    attachments = [str(uuid4()) for _ in range(100)]
    references = [uuid4() for _ in range(100)]
    Send(attachmentIds=attachments, referencePictureIds=references)
    with pytest.raises(ValidationError):
        Send(attachmentIds=attachments + ['extra'], referencePictureIds=references)
    with pytest.raises(ValidationError):
        Send(attachmentIds=attachments, referencePictureIds=references + [uuid4()])

@pytest.mark.parametrize('declared', [True, False])
def test_real_500mb_multipart_stream(declared):
    import asyncio
    from starlette.requests import Request
    from app.modules.files.multipart import parse_upload

    async def check(size):
        boundary = 'limits-boundary'
        prefix = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                  'filename="large.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()
        suffix = f'\r\n--{boundary}--\r\n'.encode()
        async def chunks():
            yield prefix
            remaining = size
            chunk = b'x' * (1024 * 1024)
            while remaining:
                part = chunk[:min(remaining, len(chunk))]
                yield part
                remaining -= len(part)
            yield suffix
        iterator = chunks().__aiter__()
        async def receive():
            try:
                return {'type': 'http.request', 'body': await anext(iterator), 'more_body': True}
            except StopAsyncIteration:
                return {'type': 'http.request', 'body': b'', 'more_body': False}
        headers = [(b'content-type', f'multipart/form-data; boundary={boundary}'.encode())]
        if declared:
            headers.append((b'content-length', str(len(prefix) + size + len(suffix)).encode()))
        request = Request({'type': 'http', 'headers': headers}, receive)
        return await parse_upload(request, MAX_UPLOAD_BYTES, maximum=MAX_UPLOAD_BYTES, size_label='500 MB')

    async def run():
        form, file = await check(MAX_UPLOAD_BYTES)
        try:
            assert file.size == MAX_UPLOAD_BYTES
        finally:
            await form.close()
        with pytest.raises(HTTPException) as caught:
            await check(MAX_UPLOAD_BYTES + 65537)
        assert caught.value.status_code == 413
        assert '500 MB' in caught.value.detail
    asyncio.run(run())
