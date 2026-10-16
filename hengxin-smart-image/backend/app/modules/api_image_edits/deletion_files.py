"""Freeze exclusive file ownership before any irreversible storage operation."""
from uuid import UUID
from sqlalchemy import or_, select
from app.models import utcnow
from app.modules.files.variants import ImageVariants
from app.retention.objects import contains_id
from .conversation_models import Conversation, ConversationTurn
from .models import ApiFile, ApiItem, ApiTask, ApiVersion


def identities(value):
    if isinstance(value, dict):
        return set().union(*(identities(v) for v in value.values())) if value else set()
    if isinstance(value, (list, tuple)):
        return set().union(*(identities(v) for v in value)) if value else set()
    try:
        return {UUID(str(value))}
    except (ValueError, TypeError):
        return set()


def related(session, task):
    items = session.scalars(select(ApiItem).where(ApiItem.task_id == task.id)).all()
    item_ids = [i.id for i in items]
    conversations = session.scalars(select(Conversation).where(Conversation.item_id.in_(item_ids))).all()
    conversation_ids = [c.id for c in conversations]
    turns = session.scalars(select(ConversationTurn).where(ConversationTurn.conversation_id.in_(conversation_ids))).all()
    files = {task.material_id}
    for item in items:
        files.update((item.source_id, item.result_id, item.revision_source_id,
                      item.revision_annotation_id, item.staging_file_id))
        files.update(identities((item.revision_snapshot or {}).get('fileIds', [])))
    for version in session.scalars(select(ApiVersion).where(ApiVersion.item_id.in_(item_ids))):
        files.update((version.file_id, version.annotation_id))
    for turn in turns:
        files.update((turn.base_file_id, turn.annotation_id, turn.candidate_id))
        files.update(identities(turn.snapshot.get('fileIds', [])))
    return items, conversations, turns, files - {None}


def shared(session, task_id, record):
    file_id = record.id
    refs = [select(ApiTask.id).where(ApiTask.id != task_id, ApiTask.material_id == file_id),
        select(ApiItem.id).where(ApiItem.task_id != task_id, or_(*(getattr(ApiItem, name) == file_id for name in
            ('source_id', 'result_id', 'revision_source_id', 'revision_annotation_id', 'staging_file_id')))),
        select(ApiVersion.id).join(ApiItem).where(ApiItem.task_id != task_id,
            or_(ApiVersion.file_id == file_id, ApiVersion.annotation_id == file_id)),
        select(ConversationTurn.id).join(Conversation).join(ApiItem).where(ApiItem.task_id != task_id,
            or_(*(getattr(ConversationTurn, name) == file_id for name in ('base_file_id', 'annotation_id', 'candidate_id'))))]
    if any(session.scalar(query.limit(1)) for query in refs):
        return True
    snapshots = [select(ApiItem.revision_snapshot).where(ApiItem.task_id != task_id),
        select(ConversationTurn.snapshot).join(Conversation).join(ApiItem).where(ApiItem.task_id != task_id)]
    if any(contains_id(tuple(row), file_id) for query in snapshots for row in session.execute(query)):
        return True
    return bool(session.scalar(select(ApiFile.id).where(ApiFile.id != record.id,
        ApiFile.bucket == record.bucket, ApiFile.object_key == record.object_key).limit(1)))


def freeze(session, task):
    _, conversations, _, files = related(session, task)
    owned = []
    for file_id in sorted(files, key=str):
        record = session.scalar(select(ApiFile).where(ApiFile.id == file_id).with_for_update(nowait=True))
        if record is None or shared(session, task.id, record):
            continue
        variant = session.scalar(select(ImageVariants).where(ImageVariants.domain == 'api-image-edits',
            ImageVariants.file_id == file_id).with_for_update(nowait=True))
        if variant and variant.lease_until is not None:
            raise RuntimeError('Thumbnail execution has not stopped')
        record.status = 'deleting'  # Durable fence: new tasks cannot reuse half-erased objects.
        owned.append(str(file_id))
    return {'files': owned, 'conversations': [str(c.id) for c in conversations]}


def objects(session, manifest, store):
    """Exact original plus the file's private derivative prefix, including interrupted writes."""
    output = set()
    for file_id in manifest['files']:
        record = session.scalar(select(ApiFile).where(ApiFile.id == UUID(file_id)).with_for_update(nowait=True))
        if not record or record.status != 'deleting':
            raise RuntimeError('Deletion file ownership changed')
        variant = session.scalar(select(ImageVariants).where(ImageVariants.domain == 'api-image-edits',
            ImageVariants.file_id == record.id).with_for_update(nowait=True))
        if variant and variant.lease_until is not None:
            raise RuntimeError('Thumbnail execution has not stopped')
        prefix = f'derived/api-image-edits/{file_id}/'
        keys = {record.object_key}
        if variant:
            keys.update(prefix + f'v1-{size}-{data["checksum"]}.webp' for size, data in variant.outputs.items())
        for key in store.keys(record.bucket, prefix):
            if not key.startswith(prefix):
                raise ValueError('Object listing escaped the owned file prefix')
            keys.add(key)
        for key in keys:
            # Also protect unusual historical aliases of a derivative key.
            for model in (ApiFile,):
                query = select(model.id).where(model.bucket == record.bucket, model.object_key == key)
                if model is ApiFile:
                    query = query.where(ApiFile.id != record.id)
                if session.scalar(query.limit(1)):
                    raise RuntimeError('Storage object is shared')
            output.add((record.bucket, key))
    return sorted(output)
