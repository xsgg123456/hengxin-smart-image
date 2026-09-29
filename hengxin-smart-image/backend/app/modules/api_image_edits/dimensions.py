"""Per-source request sizing and bounded, lossless-format result normalization."""
from fractions import Fraction
from io import BytesIO
from types import SimpleNamespace

from fastapi import HTTPException
from PIL import Image

from app.modules.files.validation import _decode_image


def request_dimensions(width, height):
    if width <= 0 or height <= 0:
        raise ValueError('Invalid source dimensions')
    if width == height:
        return 1024, 1024

    def candidates(edge):
        first = (edge + 15) // 16 * 16
        upper = max(first, edge * 102 // 100)
        return range(first, upper + 1, 16)

    ratio = Fraction(width, height)
    return min(((w, h) for w in candidates(width) for h in candidates(height)),
               key=lambda pair: (abs(Fraction(*pair) - ratio),
                                 Fraction(pair[0], width) + Fraction(pair[1], height),
                                 *pair))


def normalize_result(image, width, height, limit):
    # Called inside DECODE_SLOTS, including encoding and validation of the output.
    if width <= 0 or height <= 0 or width * height > Image.MAX_IMAGE_PIXELS:
        raise HTTPException(422, '图片解码尺寸超出安全限制')
    if image.content_type == 'image/png' and (image.width, image.height) == (width, height):
        return image
    with Image.open(BytesIO(image.data)) as source:
        source.load()
        # Palette/1-bit images otherwise force nearest-neighbour in Pillow.
        mode = 'RGBA' if 'A' in source.getbands() or 'transparency' in source.info else 'RGB'
        with source.convert(mode) as pixels:
            output = pixels if pixels.size == (width, height) else pixels.resize(
                (width, height), Image.Resampling.LANCZOS)
            try:
                buffer = BytesIO()
                output.save(buffer, format='PNG')
            finally:
                if output is not pixels:
                    output.close()
    buffer.seek(0)
    return _decode_image(SimpleNamespace(file=buffer, filename='result.png',
                                         content_type='image/png'), limit)
