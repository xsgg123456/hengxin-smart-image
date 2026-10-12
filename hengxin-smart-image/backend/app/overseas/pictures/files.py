from hashlib import sha256
from urllib.parse import quote
from io import BytesIO
from types import SimpleNamespace
from app.modules.files.validation import validate_image
from fastapi import HTTPException, Response
from . import queries

MAX_BYTES = 10 * 1024 * 1024


def read(store, record):
    stream = None
    try:
        stream = store.open(record)
        data = stream.read(MAX_BYTES + 1)
        if len(data) != record.size_bytes or sha256(data).hexdigest() != record.checksum:
            raise ValueError('Picture integrity failure')
        image = validate_image(SimpleNamespace(file=BytesIO(data), filename=record.name, content_type=record.content_type))
        if (image.width, image.height) != (record.width, record.height):
            raise ValueError('Picture dimensions mismatch')
        return data
    except Exception:
        raise HTTPException(503, '图片读取或完整性校验失败') from None
    finally:
        if stream is not None:
            try:
                stream.close()
            finally:
                stream.release_conn()


def content(session, store, actor, picture_id, number, download):
    picture = queries.find(session, picture_id, actor)
    record = queries.version(session, picture, number)
    if not record:
        raise HTTPException(404, '图片版本不存在')
    data = read(store, record)
    return Response(data, media_type=record.content_type, headers={
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': ('attachment' if download else 'inline')
            + "; filename=\"image\"; filename*=UTF-8''" + quote(record.name, safe='')})
