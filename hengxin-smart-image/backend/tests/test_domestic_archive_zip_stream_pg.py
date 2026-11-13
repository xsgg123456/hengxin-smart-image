"""Archived image ZIPs retain integrity without full-file buffering."""
import asyncio
from hashlib import sha256
from io import BytesIO
from tempfile import TemporaryFile
import tracemalloc
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.modules.domestic_studio import archive_router, archive_service
from app.modules.domestic_studio.archive_models import ArchiveFile
from app.modules.domestic_studio.turn_models import Picture
from app.overseas.studio.files import validate_stream
from files_helpers import image_bytes
from test_domestic_archive_pg import setup_archive
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context


def test_archive_zip_streams_large_picture_and_rejects_corruption(context, database, monkeypatch):
    factory, store, actor, _, channel = setup_archive(context, database, monkeypatch)
    raw = image_bytes() + b'\0' * (64 * 1024 * 1024)
    assert validate_stream(BytesIO(raw), len(raw), 'picture.png')[1] == 'image/png'
    with factory.begin() as session:
        picture = session.scalar(select(Picture))
        picture.size_bytes, picture.checksum = len(raw), sha256(raw).hexdigest()
        store.put(picture, raw)
        archive_id = archive_service.prepare(session, actor, 'camera', channel,
            archive_service.ArchiveInput(productName='测试'), 'archive-large-zip').id
    archive_service.complete(factory, store, archive_id, actor)
    with factory() as session:
        tracemalloc.start()
        try:
            response = archive_router.download(archive_id, SimpleNamespace(id=actor), session, store)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    assert peak < 32 * 1024 * 1024
    with TemporaryFile() as temporary:
        async def collect():
            async for chunk in response.body_iterator:
                temporary.write(chunk)
        asyncio.run(collect())
        temporary.seek(0)
        digest = sha256()
        with ZipFile(temporary) as zipped, zipped.open('001.png') as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        assert digest.hexdigest() == sha256(raw).hexdigest()
    with factory() as session:
        picture = session.scalar(select(ArchiveFile).where(ArchiveFile.archive_id == archive_id,
                                                            ArchiveFile.kind == 'picture'))
        store.objects[(picture.bucket, picture.object_key)] = b'corrupt'
        with pytest.raises(HTTPException) as error:
            archive_router.download(archive_id, SimpleNamespace(id=actor), session, store)
        assert error.value.status_code == 503
