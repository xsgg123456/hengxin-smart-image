"""Private originals: metadata-only preflight and bounded streaming downloads."""
from urllib.parse import quote
from fastapi import HTTPException, Response
from app.modules.files.streaming import OwnedStreamResponse
from app.overseas import image_delivery


def deliver(store, record, *, head=False, preview=False, thumbnail=False, if_none_match=None, verify_content=False):
    if record.content_type in image_delivery.IMAGE_TYPES or thumbnail:
        return image_delivery.deliver(store, record, head=head, preview=preview,
                                      thumbnail=thumbnail, if_none_match=if_none_match)
    if preview and record.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
        raise HTTPException(422, '仅支持图片预览')
    disposition = 'inline' if preview else 'attachment'
    headers = {
        'Content-Length': str(record.size_bytes),
        'Content-Disposition': disposition + "; filename*=UTF-8''" + quote(record.name, safe=''),
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
    }
    try:
        if store.stat(record) != record.size_bytes:
            raise ValueError('Original size mismatch')
        if head:
            return Response(media_type=record.content_type, headers=headers)
        stream = None if verify_content else store.open(record)
    except Exception:
        raise HTTPException(503, '原件不存在或存储暂时不可用，请稍后重试') from None
    if verify_content:
        try:
            stream = image_delivery.original_file(store, record)
        except HTTPException as error:
            if error.status_code == 413:
                raise
            raise HTTPException(503, '归档附件读取或完整性校验失败，请联系管理员') from None
    return OwnedStreamResponse(stream, media_type=record.content_type, headers=headers)
