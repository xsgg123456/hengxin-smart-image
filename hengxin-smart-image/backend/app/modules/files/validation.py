import hashlib
import re
import warnings
from dataclasses import dataclass
from io import BytesIO
from threading import BoundedSemaphore

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
FORMATS = {'JPEG': ('image/jpeg', '.jpg'), 'PNG': ('image/png', '.png'),
           'WEBP': ('image/webp', '.webp')}
DECODE_SLOTS = BoundedSemaphore(2)


@dataclass(frozen=True)
class ValidatedImage:
    data: bytes
    name: str
    content_type: str
    checksum: str
    width: int
    height: int


def safe_name(name, extension):
    # Strip both OS path separators, control characters and misleading suffixes.
    name = (name or 'image').replace('\\', '/').rsplit('/', 1)[-1]
    name = re.sub(r'[\x00-\x1f\x7f<>:"|?*]', '_', name).strip(' .')
    stem = name.rsplit('.', 1)[0] if '.' in name else name
    return (stem[:150] or 'image') + extension


def validate_image(upload):
    with DECODE_SLOTS:
        return _decode_image(upload)


def _decode_image(upload):
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, '单张图片不能超过 10 MiB')
    if not data:
        raise HTTPException(422, '图片不能为空')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                kind = image.format
                if kind not in FORMATS:
                    raise HTTPException(422, '仅支持 JPG、PNG 和 WebP 图片')
                image.verify()
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
                frames = getattr(image, 'n_frames', 1)
                if width * height * frames > Image.MAX_IMAGE_PIXELS:
                    raise HTTPException(422, '图片解码尺寸超出安全限制')
                # Decode every frame too: corrupt later frames are not accepted.
                for frame in range(frames):
                    image.seek(frame)
                    image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, '图片损坏或解码尺寸超出安全限制') from None
    content_type, extension = FORMATS[kind]
    if upload.content_type not in (None, 'application/octet-stream', content_type):
        raise HTTPException(422, '声明的图片类型与实际内容不一致')
    return ValidatedImage(data, safe_name(upload.filename, extension), content_type,
                          hashlib.sha256(data).hexdigest(), width, height)
