"""Private originals: metadata-only preflight and bounded streaming downloads."""
from urllib.parse import quote
from fastapi import HTTPException, Response
from app.modules.files.streaming import OwnedStreamResponse


def deliver(store, record, *, head=False):
    headers = {
        'Content-Length': str(record.size_bytes),
        'Content-Disposition': "attachment; filename*=UTF-8''" + quote(record.name, safe=''),
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
    }
    try:
        if store.stat(record) != record.size_bytes:
            raise ValueError('Original size mismatch')
        if head:
            return Response(media_type=record.content_type, headers=headers)
        stream = store.open(record)
    except Exception:
        raise HTTPException(503, '原件不存在或存储暂时不可用，请稍后重试') from None
    return OwnedStreamResponse(stream, media_type=record.content_type, headers=headers)
