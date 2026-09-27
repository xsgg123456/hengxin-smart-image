"""Conditional private display delivery; invoked only AFTER current authorization."""
from fastapi import HTTPException, Response

from .internal_delivery import delivery_headers
from .streaming import OwnedStreamResponse
from .variants import representation


def deliver_variant(session, original, domain, size, request, store):
    record = representation(session, original, domain, size)
    session.close()
    headers = {**delivery_headers(record, False),
        'Cache-Control': 'private, no-cache', 'Vary': 'Cookie, Authorization',
        'ETag': f'"{record.checksum}"'}
    # Check private bucket/object availability before acknowledging cached bytes.
    try:
        if store.stat(record) != record.size_bytes:
            raise ValueError('object size changed')
        candidates = request.headers.get('if-none-match', '').split(',')
        if any(value.strip().removeprefix('W/') in (headers['ETag'], '*') for value in candidates):
            return Response(status_code=304, headers=headers)
        headers['Content-Length'] = str(record.size_bytes)
        if request.method == 'HEAD':
            return Response(headers=headers)
        stream = store.open(record)
    except Exception:
        raise HTTPException(503, '图片暂时不可读取，请稍后重试') from None
    return OwnedStreamResponse(stream, media_type=record.content_type, headers=headers)
