"""Private media hand-off. Signatures are consumed only by the internal gateway."""
import re
from urllib.parse import quote, urlsplit

from fastapi import HTTPException, Response

from app.core.config import get_settings


def delivery_headers(record, download):
    disposition = 'attachment' if download else 'inline'
    return {
        'Content-Type': record.content_type,
        'Content-Disposition': f"{disposition}; filename=image; filename*=UTF-8''{quote(record.name, safe='')}",
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
    }


def head_delivery(record, store, download=False):
    try:
        if store.stat(record) != record.size_bytes:
            raise ValueError('object size changed')
    except Exception:
        raise HTTPException(503, '图片暂时不可读取，请稍后重试') from None
    return Response(headers={**delivery_headers(record, download), 'Content-Length': str(record.size_bytes)})


def internal_delivery(record, store, request, domain, download=False):
    settings = get_settings()
    if not settings.media_internal_delivery_enabled:
        return None
    # This marker is not authentication. The opt-in media service has NO public
    # port; its only ingress is the gateway, which overwrites the client header.
    # Current user/file authorization has already run before this function.
    expected = f'{domain}/{record.id}'
    headers = delivery_headers(record, download)
    if (request.headers.get('x-hengxin-media-gateway') != '1'
            or settings.minio_endpoint != 'minio:9000' or settings.minio_secure
            or domain not in ('originals', 'api-image-edits')
            or record.bucket != settings.minio_bucket
            or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', record.bucket)
            or record.object_key != expected or request.method not in ('GET', 'HEAD')):
        raise HTTPException(503, '媒体交付配置不可用')
    try:
        target = urlsplit(store.signed_delivery(record, request.method, {
            'response-content-type': headers['Content-Type'],
            'response-content-disposition': headers['Content-Disposition'],
            'response-cache-control': headers['Cache-Control'],
        }))
        if (target.scheme != 'http' or target.netloc != 'minio:9000' or target.fragment
                or target.path != f'/{record.bucket}/{expected}' or not target.query
                or any(c in target.query for c in '\r\n#')):
            raise ValueError('invalid internal delivery target')
    except Exception:
        raise HTTPException(503, '图片暂时不可读取，请稍后重试') from None
    headers['X-Accel-Redirect'] = '/__hx_media' + target.path + '?' + target.query
    return Response(headers=headers)
