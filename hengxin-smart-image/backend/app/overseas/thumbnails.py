"""Small display derivatives with bounded input, decoded pixels, work and LRU bytes."""
from collections import OrderedDict
from io import BytesIO
from threading import BoundedSemaphore, Lock
from fastapi import HTTPException
from PIL import Image, ImageOps
from app.overseas.image_delivery import original_bytes

MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 24_000_000
MAX_SIDE = 384
MAX_RESULT_BYTES = 1024 * 1024
CACHE_BYTES = 32 * 1024 * 1024
CACHE_ITEMS = 256
WORKER_WAIT_SECONDS = 1.0
_workers = BoundedSemaphore(2)
_lock = Lock()
_cache = OrderedDict()
_cache_bytes = 0


def _cached(key):
    with _lock:
        data = _cache.get(key)
        if data is not None:
            _cache.move_to_end(key)
        return data


def _remember(key, data):
    global _cache_bytes
    with _lock:
        previous = _cache.pop(key, None)
        if previous is not None:
            _cache_bytes -= len(previous)
        _cache[key] = data
        _cache_bytes += len(data)
        while _cache and (len(_cache) > CACHE_ITEMS or _cache_bytes > CACHE_BYTES):
            _, removed = _cache.popitem(last=False)
            _cache_bytes -= len(removed)


def render(store, record):
    if record.size_bytes > MAX_SOURCE_BYTES:
        raise HTTPException(413, '原图过大，请直接查看原图')
    key = (record.bucket, record.object_key, record.checksum, record.content_type)
    data = _cached(key)
    if data is not None:
        return data
    # Briefly absorb a burst of visible cards; no source bytes are read while waiting.
    if not _workers.acquire(timeout=WORKER_WAIT_SECONDS):
        raise HTTPException(429, '缩略图处理繁忙，请稍后重试', headers={'Retry-After': '1'})
    try:
        data = _cached(key)
        if data is not None:
            return data
        source = original_bytes(store, record, MAX_SOURCE_BYTES)
        try:
            with Image.open(BytesIO(source)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise HTTPException(422, '图片格式不支持缩略图')
                if image.width * image.height > MAX_PIXELS:
                    raise HTTPException(413, '图片像素过大，请直接查看原图')
                if getattr(image, 'n_frames', 1) != 1:
                    raise HTTPException(422, '动态图请直接查看原图')
                image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
                with ImageOps.exif_transpose(image) as oriented:
                    with oriented.convert('RGBA' if 'A' in oriented.getbands() or 'transparency' in oriented.info else 'RGB') as small:
                        output = BytesIO()
                        small.save(output, 'WEBP', quality=80, method=3)
                        data = output.getvalue()
            if len(data) > MAX_RESULT_BYTES:
                raise HTTPException(413, '缩略图超过处理大小限制')
        except HTTPException:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(413, '图片像素过大，请直接查看原图') from None
        except Exception:
            raise HTTPException(422, '图片无法生成缩略图，请直接查看原图') from None
        _remember(key, data)
        return data
    finally:
        _workers.release()
