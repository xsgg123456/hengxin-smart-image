"""Authorized, bounded-memory ZIP downloads of immutable image objects."""
import hashlib
import re
from typing import Annotated
from urllib.parse import quote
from uuid import UUID
from zipfile import ZIP_STORED, ZipFile

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.modules.auth.permissions import require_permission
from app.modules.files.service import find_file
from app.modules.files.streaming import OwnedStreamResponse
from app.modules.files.validation import FORMATS, safe_name
from app.storage.minio_store import get_store

router = APIRouter(tags=['files'])
EXTENSIONS = {mime: extension for mime, extension in FORMATS.values()}


class ZipRequest(BaseModel):
    fileIds: list[UUID] = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)


class ChunkSink:
    """Unseekable ZipFile target drained after every bounded object chunk."""
    def __init__(self):
        self.parts = []

    def write(self, data):
        if data:
            self.parts.append(data)
        return len(data)

    def flush(self):
        pass

    def drain(self):
        parts, self.parts = self.parts, []
        return parts


class ZipStream:
    def __init__(self, records, store):
        self.sources = []
        self.iterator = None
        try:
            # Open before response headers so missing objects produce a visible 503.
            for record in records:
                self.sources.append((record, store.open(record)))
        except Exception:
            self.close()
            raise HTTPException(503, '图片暂时不可读取，请稍后重试') from None

    def stream(self, chunk_size):
        self.iterator = self.generate(chunk_size)
        return self.iterator

    def generate(self, chunk_size):
        sink = ChunkSink()
        with ZipFile(sink, 'w', compression=ZIP_STORED) as archive:
            for index, (record, source) in enumerate(self.sources, 1):
                name = f'{index:02d}-{safe_name(record.name, EXTENSIONS[record.content_type])}'
                digest, count = hashlib.sha256(), 0
                with archive.open(name, 'w', force_zip64=True) as target:
                    yield from sink.drain()
                    for chunk in source.stream(chunk_size):
                        count += len(chunk)
                        if count > record.size_bytes:
                            raise OSError('Stored image size mismatch')
                        digest.update(chunk)
                        target.write(chunk)
                        yield from sink.drain()
                    if count != record.size_bytes or digest.hexdigest() != record.checksum:
                        raise OSError('Stored image integrity mismatch')
                yield from sink.drain()
        yield from sink.drain()

    def close(self):
        try:
            if self.iterator is not None:
                self.iterator.close()
        finally:
            # Attempt every release even if one upstream connection fails to close.
            sources, self.sources = self.sources, []
            for _, source in sources:
                try:
                    source.close()
                except Exception:
                    pass
                try:
                    source.release_conn()
                except Exception:
                    pass

    def release_conn(self):
        pass


@router.post('/files/download-zip')
def download_zip(body: ZipRequest,
                 user: Annotated[object, Depends(require_permission('shared_resources'))],
                 session: Annotated[Session, Depends(get_session)], store=Depends(get_store)):
    records = [find_file(session, file_id) for file_id in body.fileIds]
    if any(record.content_type not in EXTENSIONS for record in records):
        raise HTTPException(422, '图片格式不支持下载')
    name = safe_name(body.name, '.zip')
    if re.match(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', name, re.I):
        name = '图片_' + name
    return OwnedStreamResponse(ZipStream(records, store), media_type='application/zip', headers={
        'Content-Disposition': f"attachment; filename=\"images.zip\"; filename*=UTF-8''{quote(name, safe='')}",
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
        'X-Accel-Buffering': 'no',
    })
