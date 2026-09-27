"""Retryable delivery persistence with stable round/slot/content identities."""
import json
from uuid import UUID, NAMESPACE_URL, uuid5

from app.core.config import get_settings
from app.resource_models import FileRecord
from .delivery_snapshot import image_metadata


class DeliveryOwnershipLost(RuntimeError):
    """Caller must stop without publishing after execution ownership is lost."""


class DeliveryStorageConflict(ValueError):
    """An existing identity does not belong to this exact delivery."""


def _check(active):
    if not active():
        raise DeliveryOwnershipLost('Delivery execution ownership was lost')


def _record_fields(operator_id, round_id, slot, image):
    meta = image_metadata(image)
    identity = json.dumps([str(UUID(str(round_id))), slot, meta], sort_keys=True)
    file_id = uuid5(NAMESPACE_URL, 'hengxin:delivery:v1:' + identity)
    return dict(id=file_id, owner_id=UUID(str(operator_id)), name=image.name,
                bucket=get_settings().minio_bucket, object_key=f'originals/{file_id}',
                content_type=image.content_type, checksum=image.checksum,
                size_bytes=len(image.data), width=image.width, height=image.height)


def _verify(record, fields):
    if (record.deleted_at is not None
            or any(getattr(record, key) != value for key, value in fields.items())
            or record.status not in ('staging', 'failed', 'ready')):
        raise DeliveryStorageConflict('Stored delivery identity or owner mismatch')


def store_delivery(factory, store, operator_id, round_id, images, active):
    """Persist each slot idempotently; ambiguous commits never delete objects."""
    result = []
    for slot, image in enumerate(images):
        _check(active)
        fields = _record_fields(operator_id, round_id, slot, image)
        with factory() as session:
            record = session.get(FileRecord, fields['id'])
            if record is None:
                record = FileRecord(**fields, status='staging')
                session.add(record)
                # A retry re-reads this deterministic ID after any ambiguous commit.
                session.commit()
            _verify(record, fields)
            _check(active)
            if record.status != 'ready':
                # A failed PUT may have succeeded remotely. Keep staging and never remove.
                store.put(record, image.data)
                _check(active)
                session.refresh(record)
                _verify(record, fields)
                _check(active)
                record.status = 'ready'
                session.commit()
            _check(active)
            result.append(fields['id'])
    return result
