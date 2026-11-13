"""Retain original files; image decoding only selects the existing picture UI."""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from PIL import Image
from fastapi import HTTPException

from app.modules.files.validation import ValidatedImage
from .files import MAX_BYTES, _KeepOpen, validate, validate_stream


@dataclass(frozen=True)
class DeliveredFile:
    data: bytes
    name: str
    content_type: str
    checksum: str
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class FileMetadata:
    name: str
    content_type: str
    checksum: str
    size_bytes: int
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class FileRef:
    path: Path
    name: str
    content_type: str
    checksum: str
    size_bytes: int
    width: int | None = None
    height: int | None = None


def inspect_stream(stream, size, name):
    """Inspect a seekable original without retaining its full bytes in memory."""
    if type(size) is not int or not 0 <= size <= MAX_BYTES:
        raise HTTPException(413, '单个文件不能超过 500 MB')
    digest, read = sha256(), 0
    stream.seek(0)
    while chunk := stream.read(1024 * 1024):
        read += len(chunk)
        if read > size:
            raise ValueError('Output grew while reading')
        digest.update(chunk)
    if read != size:
        raise ValueError('Output size changed while reading')
    stream.seek(0)
    name, kind = validate_stream(stream if size else BytesIO(b'\0'), size or 1, name)
    width = height = None
    if size and kind in ('image/png', 'image/jpeg', 'image/webp'):
        stream.seek(0)
        with Image.open(_KeepOpen(stream)) as image:
            width, height = image.size
    stream.seek(0)
    return FileMetadata(name, kind, digest.hexdigest(), size, width, height)


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
