"""Retain original files; image decoding only selects the existing picture UI."""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image
from fastapi import HTTPException

from app.modules.files.validation import ValidatedImage
from .files import MAX_BYTES, validate


@dataclass(frozen=True)
class DeliveredFile:
    data: bytes
    name: str
    content_type: str
    checksum: str
    width: int | None = None
    height: int | None = None


def validated(data, name, content_type=None):
    if not isinstance(data, bytes):
        raise ValueError('Invalid output bytes')
    if len(data) > MAX_BYTES:
        raise HTTPException(413, '单个文件不能超过 500 MB')
    # Input uploads keep their non-empty contract; output files may be 0 B.
    name, kind = validate(data if data else b'\0', name)
    checksum = sha256(data).hexdigest()
    if data and kind in ('image/png', 'image/jpeg', 'image/webp'):
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
        return ValidatedImage(data, name, kind, checksum, width, height)
    return DeliveredFile(data, name, kind, checksum)
