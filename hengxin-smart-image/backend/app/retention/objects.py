"""Reference-aware object removal with durable, retryable storage receipts."""
from datetime import timedelta
from uuid import UUID
from sqlalchemy import or_, select
from app.models import utcnow
from app.modules.api_image_edits.models import ApiFile, ApiItem, ApiTask, ApiVersion
from app.modules.api_image_edits.conversation_models import ConversationTurn
from app.modules.files.variants import ImageVariants
from .models import RetentionObject
from .observability_models import RetentionObjectLink
from .events import object_result
from .state import aware


def contains_id(value, file_id):
    if isinstance(value, dict):
        return any(contains_id(v, file_id) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_id(v, file_id) for v in value)
    return str(value) == str(file_id)


def referenced(session, domain, file_id):
    if domain != 'api-image-edits':
        raise ValueError('Invalid file domain')
    refs = [(ApiTask, ('material_id',)), (ApiItem, ('source_id', 'result_id',
            'revision_source_id', 'revision_annotation_id', 'staging_file_id')),
            (ApiVersion, ('file_id', 'annotation_id')),
            (ConversationTurn, ('base_file_id', 'annotation_id', 'candidate_id'))]
    for model, columns in refs:
        if session.scalar(select(model.id).where(or_(
                *(getattr(model, c) == file_id for c in columns))).limit(1)):
            return True
    # Frozen JSON references have no database FK. Keep them even on deleted tasks.
    for model, columns in [(ConversationTurn, ('snapshot',)), (ApiItem, ('revision_snapshot',))]:
        for values in session.execute(select(*(getattr(model, c) for c in columns))):
            if contains_id(tuple(values), file_id):
                return True
    return False


def queue_unused(session, domain, file_ids, now=None, receipt=None):
    now = now or utcnow()
    model = ApiFile
    if domain != 'api-image-edits':
        raise ValueError('Invalid file domain')
    session.flush()
    removed = 0
    for file_id in sorted(set(file_ids), key=str):
        if file_id is None:
            continue
        file_id = UUID(str(file_id))
        record = session.scalar(select(model).where(model.id == file_id).with_for_update(nowait=True))
        if not record or referenced(session, domain, file_id):
            continue
        if session.scalar(select(ApiFile.id).where(ApiFile.id != record.id,
                ApiFile.bucket == record.bucket, ApiFile.object_key == record.object_key).limit(1)):
            continue
        variant = session.scalar(select(ImageVariants).where(ImageVariants.domain == domain,
            ImageVariants.file_id == file_id).with_for_update(nowait=True))
        if variant and variant.lease_until is not None:
            raise RuntimeError('Thumbnail ownership is unresolved; retry after reconciliation')
        keys = [record.object_key]
        if variant:
            for size, data in variant.outputs.items():
                keys.append(f'derived/{domain}/{file_id}/v1-{size}-{data["checksum"]}.webp')
            session.delete(variant)
        for key in keys:
            obj = session.scalar(select(RetentionObject).where(
                    RetentionObject.bucket == record.bucket, RetentionObject.object_key == key))
            if obj is None:
                obj = RetentionObject(bucket=record.bucket, object_key=key, next_attempt_at=now)
                session.add(obj)
                session.flush()
            if receipt is not None and not session.scalar(select(RetentionObjectLink.id).where(
                    RetentionObjectLink.record_id == receipt.id, RetentionObjectLink.object_id == obj.id)):
                session.add(RetentionObjectLink(record_id=receipt.id, object_id=obj.id))
                receipt.objects_pending += 1
        session.delete(record)
        removed += 1
    return removed


def retry_objects(factory, store, limit=25, now=None):
    now = now or utcnow()
    removed = 0
    with factory() as session:
        ids = session.scalars(select(RetentionObject.id).where(RetentionObject.next_attempt_at <= now)
            .order_by(RetentionObject.next_attempt_at, RetentionObject.id).limit(limit)).all()
    for identifier in ids:
        with factory.begin() as session:
            row = session.scalar(select(RetentionObject).where(RetentionObject.id == identifier)
                                 .with_for_update(skip_locked=True))
            if row is None or aware(row.next_attempt_at) > aware(now):
                continue
            # Last line of defence if a key has been reintroduced after the receipt.
            if any(session.scalar(select(model.id).where(model.bucket == row.bucket,
                    model.object_key == row.object_key).limit(1))
                    for model in (ApiFile,)):
                row.next_attempt_at = now + timedelta(hours=1)
                object_result(session, row.id, now, protected=True, next_attempt=row.next_attempt_at)
                continue
            try:
                store.remove(row)
            except Exception:
                row.attempts += 1
                row.next_attempt_at = now + timedelta(hours=1)
                object_result(session, row.id, now, next_attempt=row.next_attempt_at)
            else:
                object_result(session, row.id, now, removed=True)
                session.delete(row)
                removed += 1
    return removed
