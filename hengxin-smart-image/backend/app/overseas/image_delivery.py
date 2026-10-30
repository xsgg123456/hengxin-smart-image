"""Authenticated image representations; callers authorize and capture records first."""
from hashlib import sha256
from urllib.parse import quote
from fastapi import HTTPException, Response
from app.overseas.upload_limits import MAX_UPLOAD_BYTES

IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/webp')


def original_bytes(store, record, limit=MAX_UPLOAD_BYTES):
    stream = None
    try:
        if record.size_bytes > limit:
            raise HTTPException(413, '图片超过处理大小限制')
        stream = store.open(record)
        data = stream.read(limit + 1)
        if len(data) != record.size_bytes or sha256(data).hexdigest() != record.checksum:
            raise ValueError('Image integrity failure')
        return data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, '图片读取或完整性校验失败') from None
    finally:
        if stream is not None:
            try:
                stream.close()
            finally:
                stream.release_conn()


def matches(value, etag):
    # GET and HEAD use weak comparison, including a list of validators.
    return any(item.strip().removeprefix('W/') in ('*', etag)
               for item in (value or '').split(','))


def deliver(store, record, *, head=False, preview=False, thumbnail=False, if_none_match=None):
    if record.content_type not in IMAGE_TYPES:
        raise HTTPException(422, '仅支持图片预览')
    # Existence/privacy checks are never bypassed by a matching validator or derivative.
    try:
        if store.stat(record) != record.size_bytes:
            raise ValueError('Original size mismatch')
    except Exception:
        raise HTTPException(503, '原件不存在或存储暂时不可用，请稍后重试') from None
    data = None
    etag, size, content_type = f'"{record.checksum}"', record.size_bytes, record.content_type
    if thumbnail:
        from app.overseas.thumbnails import render
        data = render(store, record)
        etag, size, content_type = f'"thumbnail-{sha256(data).hexdigest()}"', len(data), 'image/webp'
    disposition = 'inline' if preview or thumbnail else 'attachment'
    headers = {
        'ETag': etag, 'Cache-Control': 'private, no-cache',
        'Vary': 'Cookie, Authorization', 'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': disposition + "; filename*=UTF-8''" + quote(record.name, safe=''),
    }
    if matches(if_none_match, etag):
        return Response(status_code=304, headers=headers)
    headers['Content-Length'] = str(size)
    if head:
        return Response(media_type=content_type, headers=headers)
    if data is None:
        data = original_bytes(store, record)
    return Response(data, media_type=content_type, headers=headers)
