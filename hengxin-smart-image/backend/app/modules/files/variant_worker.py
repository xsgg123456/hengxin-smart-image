"""Single-process bounded image consumer, independent of paid generation workers."""
import argparse
import hashlib
import logging
import signal
import threading
import warnings
from dataclasses import replace
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageOps
from sqlalchemy import or_, select

from app.models import utcnow
from .delivery import FileDelivery
from .variants import ImageVariants, SIZES, backfill


def encode(data):
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(BytesIO(data)) as source:
            if source.width * source.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError('image exceeds decoder limit')
            # Display derivatives use the first frame; original animation is preserved.
            source.seek(0)
            source.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            oriented = ImageOps.exif_transpose(source)
            try:
                image = oriented.convert('RGBA' if 'A' in oriented.getbands()
                                         or 'transparency' in oriented.info else 'RGB')
                try:
                    for size in reversed(SIZES):
                        image.thumbnail((size, size), Image.Resampling.LANCZOS)
                        output = BytesIO()
                        image.save(output, 'WEBP', quality=82, method=4)
                        yield size, output.getvalue()
                finally:
                    image.close()
            finally:
                if oriented is not source:
                    oriented.close()


def process_one(factory, store):
    from app.resource_models import FileRecord
    from app.modules.api_image_edits.models import ApiFile
    now, token = utcnow(), uuid4()
    with factory.begin() as session:
        row = session.scalar(select(ImageVariants).where(
            ImageVariants.completed.is_(False), ImageVariants.next_attempt <= now,
            or_(ImageVariants.lease_until.is_(None), ImageVariants.lease_until <= now)
        ).order_by(ImageVariants.next_attempt).limit(1).with_for_update(skip_locked=True))
        if row is None:
            return False
        key, source_hash = (row.domain, row.file_id), row.source_checksum
        model = FileRecord if row.domain == 'originals' else ApiFile
        source = session.get(model, row.file_id)
        if source is None or source.deleted_at or source.status != 'ready':
            row.completed = True
            return True
        original = FileDelivery.capture(source)
        row.token, row.lease_until = token, now + timedelta(minutes=10)
        row.attempts += 1
    outputs, error = {}, None
    try:
        # Existing upload/result limits are smaller; bound corrupt metadata too.
        if original.checksum != source_hash or not 0 < original.size_bytes <= 64 * 1024**2:
            raise ValueError('invalid source metadata')
        stream = store.open(original)
        try:
            data = bytearray()
            for chunk in stream.stream(64 * 1024):
                data.extend(chunk)
                if len(data) > original.size_bytes:
                    raise ValueError('source length changed')
        finally:
            try:
                stream.close()
            finally:
                stream.release_conn()
        if len(data) != original.size_bytes or hashlib.sha256(data).hexdigest() != source_hash:
            raise ValueError('source checksum changed')
        for size, content in encode(data):
            checksum = hashlib.sha256(content).hexdigest()
            derived = replace(original,
                object_key=f'derived/{key[0]}/{original.id}/v1-{size}-{checksum}.webp',
                content_type='image/webp', checksum=checksum, size_bytes=len(content))
            store.put(derived, content)
            outputs[str(size)] = {'checksum': checksum, 'size': len(content)}
    except Exception as exc:
        error = type(exc).__name__
    with factory.begin() as session:
        row = session.get(ImageVariants, key, with_for_update=True)
        if row and row.token == token:
            row.token = row.lease_until = None
            if error:
                row.next_attempt = utcnow() + timedelta(seconds=min(3600, 5 * 2**min(row.attempts, 10)))
                logging.warning('Image variant retry: %s/%s (%s)', *key, error)
            else:
                row.outputs, row.completed = outputs, True
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backfill', action='store_true')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    from app.db.session import session_factory
    from app.storage.minio_store import get_store
    factory, store, stopped = session_factory(), get_store(), threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopped.set())
    while not stopped.is_set():
        try:
            if args.backfill:
                backfill(factory, 20)
            worked = process_one(factory, store)
        except Exception:
            if args.once:
                raise
            logging.warning('Image variant consumer unavailable; durable work retained')
            worked = False
        if args.once:
            break
        stopped.wait(0.05 if worked else 2)


if __name__ == '__main__':
    main()
