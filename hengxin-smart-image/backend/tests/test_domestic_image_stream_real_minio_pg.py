"""Large real PNG previews and downloads remain bounded and integrity checked."""
import asyncio
from hashlib import sha256
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import tracemalloc
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from PIL import Image

from app.modules.domestic_studio import file_service, router
from app.modules.domestic_studio.turn_models import Upload
from app.overseas import image_delivery
from test_domestic_late_outputs_real_minio_pg import storage
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context


@pytest.mark.skipif(os.environ.get('TEST_DOMESTIC_MINIO_LARGE') != '1',
                    reason='requires an explicit large-file local MinIO test')
def test_large_real_png_preview_and_download_stream_after_integrity_check(context, database, tmp_path, monkeypatch, storage):
    factory, _, _, actor, _, channel, _ = context
    store, bucket, _, _ = storage
    with TemporaryDirectory(dir=tmp_path) as root:
        path = Path(root) / 'real.png'
        pixels = os.urandom(4096 * 4096 * 3)
        with Image.frombytes('RGB', (4096, 4096), pixels) as image:
            image.save(path, 'PNG', compress_level=0)
        del pixels
        assert path.stat().st_size > 32 * 1024 * 1024
        settings = SimpleNamespace(app_env='test', minio_bucket=bucket, codex_execution_root=root)
        monkeypatch.setattr(file_service, 'get_settings', lambda: settings)
        with path.open('rb') as source:
            uploaded = file_service.upload(factory, store, actor, 'camera', channel, source, 'real.png')
        identity = UUID(uploaded['id'].removeprefix('upload:'))
        with factory() as session:
            row = session.get(Upload, identity)
            expected_size, expected_hash = row.size_bytes, row.checksum
            assert row.content_type == 'image/png'
        for preview in (True, False):
            with factory() as session:
                tracemalloc.start()
                try:
                    response = router.content(session, store, SimpleNamespace(id=actor), 'camera', identity,
                        kind='files', request=SimpleNamespace(headers={}), preview=preview)
                    digest, length = sha256(), 0
                    async def send(message):
                        nonlocal length
                        if message['type'] == 'http.response.body':
                            data = message.get('body', b'')
                            length += len(data)
                            digest.update(data)
                    async def receive():
                        return {'type':'http.disconnect'}
                    asyncio.run(response({'type':'http', 'asgi':{'spec_version':'2.4'}}, receive, send))
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
            assert peak < 32 * 1024 * 1024
            assert length == expected_size and digest.hexdigest() == expected_hash
            assert response.stream.closed
            assert response.headers['content-disposition'].startswith('inline' if preview else 'attachment')
        with factory.begin() as session:
            session.get(Upload, identity).checksum = '0' * 64
        with factory() as session:
            with pytest.raises(HTTPException) as error:
                router.content(session, store, SimpleNamespace(id=actor), 'camera', identity,
                    kind='files', request=SimpleNamespace(headers={}), preview=True)
            assert error.value.status_code == 503
