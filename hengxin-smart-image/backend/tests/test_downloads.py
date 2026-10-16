from test_api_image_domain import enabled_api
import asyncio
import hashlib
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

import pytest

from app.modules.api_image_edits.zip_download import ZipStream
from app.modules.files.streaming import OwnedStreamResponse
from app.resource_models import UserRecord
from files_helpers import files_env, image_bytes
from test_files import upload
















@pytest.mark.parametrize('fail_after', [0, 2])
def test_disconnect_before_and_during_iteration_closes_all(fail_after):
    source = BytesIO(b'a' * 1024 * 1024)
    stream = ZipStream(source)
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
    assert source.closed


