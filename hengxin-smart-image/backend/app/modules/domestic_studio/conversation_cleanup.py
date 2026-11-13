"""On the original worker, erase only resources proven to belong to one session."""
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.models import Job, Outbox
from app.overseas.studio.files import verify
from app.overseas.tasks import cleanup_files, cleanup_process
from app.storage.minio_store import get_store
from app.worker.leases import TERMINAL
from .archive_models import Archive, ArchiveDeletion, ArchiveFile
from . import maintenance_lock, output_intents
from .archive_service import archive_key, verify_snapshot
from .bindings import lock_admission
from .conversation_models import Conversation, ConversationDeletion, Workspace
from .models import SkillExecutionReference
from .turn_models import OutputFile, Picture, Transcript, Turn, Upload


def confirmed(session, identity, settings):
    rows = session.execute(select(Turn, Job).join(Job, Job.id == Turn.job_id)
                           .where(Turn.conversation_id == identity)).all()
    for turn, job in rows:
        if job.status not in TERMINAL:
            return False
        if not turn.dispatched:
            continue
        process = turn.process_identity
        if (not isinstance(process, dict) or process.get('node') != settings.worker_node_name
                or type(process.get('pid')) is not int or process['pid'] <= 1
                or not isinstance(process.get('boot'), str) or not process['boot']
                or not isinstance(process.get('birth'), str) or not process['birth']):
            return False
        try:
            if cleanup_process.group_alive(SimpleNamespace(process_boot=process['boot'], process_id=process['pid'])):
                return False
        except (OSError, ValueError):
            return False
    return True


def archive_copies(session, store, channel):
    records = session.scalars(select(Archive).where(Archive.source_conversation_id == channel.id)
                              .with_for_update()).all()
    for record in records:
        if (record.owner_id != channel.owner_id or record.workspace != channel.workspace
                or record.status != 'ready' or session.get(ArchiveDeletion, record.id)):
            raise ValueError('Archive state is not independently protected')
        rows = list(session.scalars(select(ArchiveFile).where(ArchiveFile.archive_id == record.id)))
        verify_snapshot(record, rows)
        for row in rows:
            expected = archive_key(record, row.id)
            if row.status != 'ready' or row.object_key != expected:
                raise ValueError('Archive copy ownership mismatch')
            verify(store, row)


def prefixes(channel):
    path = f'{channel.owner_id}/{channel.workspace}/{channel.id}/'
    return ('domestic-studio/uploads/' + path, 'domestic-studio/outputs/' + path)


def validate(manifest, channel):
    if (not isinstance(manifest, dict) or manifest.get('directories') != ['domestic-studio/' + str(channel.id)]
            or not isinstance(manifest.get('objects'), list)):
        raise ValueError('Invalid cleanup manifest')
    for item in manifest['objects']:
        if not isinstance(item, dict) or set(item) != {'bucket', 'object_key'}:
            raise ValueError('Invalid cleanup object')
        bucket, key = item['bucket'], item['object_key']
        if (not isinstance(bucket, str) or not bucket or not isinstance(key, str)
                or not any(key.startswith(prefix) for prefix in prefixes(channel))
                or PurePosixPath(key).is_absolute() or '..' in PurePosixPath(key).parts
                or '\\' in key or ':' in key):
            raise ValueError('Cleanup object escaped its conversation')
    cleanup_files.validate_directories(manifest, namespaces=('domestic-studio',))


def inventory(session, store, channel, settings):
    turns = list(session.scalars(select(Turn).where(Turn.conversation_id == channel.id)))
    turn_ids = [turn.id for turn in turns]
    sources = list(session.scalars(select(Upload).where(Upload.conversation_id == channel.id)))
    for upload in sources:
        if upload.status != 'ready':
            if upload.status != 'uploading':
                raise ValueError('Unknown attachment write state')
            # A finished, integrity-checked object proves this unique PUT has
            # reached storage; an absent object may still be written later.
            verify(store, upload)
    published = {}
    for model in (Picture, OutputFile):
        rows = list(session.scalars(select(model).where(model.turn_id.in_(turn_ids))))
        sources.extend(rows)
        published.update({str(row.id): row for row in rows})
    objects = {(row.bucket, row.object_key) for row in sources}
    for turn in turns:
        objects.update(output_intents.inventory(turn, channel, published, store))
    for bucket in {settings.minio_bucket, *(bucket for bucket, _ in objects)}:
        for prefix in prefixes(channel):
            for key in store.keys(bucket, prefix):
                if not key.startswith(prefix):
                    raise ValueError('Storage listing escaped requested namespace')
                objects.add((bucket, key))
    for bucket, key in objects:
        if session.scalar(select(ArchiveFile.id).where(ArchiveFile.bucket == bucket,
                                                       ArchiveFile.object_key == key).limit(1)):
            raise ValueError('Archive file must be independent')
    manifest = dict(objects=[dict(bucket=bucket, object_key=key) for bucket, key in sorted(objects)],
        directories=['domestic-studio/' + str(channel.id)], root=str(Path(settings.codex_execution_root).absolute()))
    validate(manifest, channel)
    return manifest


def erase_records(session, identity):
    turns = list(session.scalars(select(Turn.id).where(Turn.conversation_id == identity)))
    jobs = list(session.scalars(select(Turn.job_id).where(Turn.conversation_id == identity)))
    for model, condition in ((Transcript, Transcript.turn_id.in_(turns)),
        (Picture, Picture.turn_id.in_(turns)), (OutputFile, OutputFile.turn_id.in_(turns)),
        (Upload, Upload.conversation_id == identity), (Turn, Turn.id.in_(turns)),
        (SkillExecutionReference, SkillExecutionReference.job_id.in_(jobs)),
        (Outbox, Outbox.job_id.in_(jobs)), (Job, Job.id.in_(jobs)), (Conversation, Conversation.id == identity)):
        session.execute(delete(model).where(condition).execution_options(synchronize_session=False))


def locked(session, identity):
    # The committed deletion receipt blocks new source writes and archive
    # deletion. Only its own row is locked across file operations.
    channel = session.get(Conversation, identity)
    receipt = session.scalar(select(ConversationDeletion).where(ConversationDeletion.conversation_id == identity)
                             .with_for_update(skip_locked=True).execution_options(populate_existing=True))
    if (receipt is None or receipt.status != 'deleting' or channel is None
            or receipt.owner_id != channel.owner_id or receipt.workspace != channel.workspace):
        return None, None
    return channel, receipt


def process(factory, store, identity):
    settings = get_settings()
    try:
        with maintenance_lock.hold(settings, identity):
            return _process(factory, store, identity, settings)
    except (OSError, ValueError):
        return False


def _process(factory, store, identity, settings):
    try:
        with factory.begin() as session:
            channel, receipt = locked(session, identity)
            if receipt is None:
                return False
            if not confirmed(session, identity, settings):
                raise ValueError('Original execution exit not verified on this worker')
            archive_copies(session, store, channel)
            if not receipt.manifest:
                receipt.manifest = inventory(session, store, channel, settings)
        # The proof and object inventory survive a worker crash before erasure.
        with factory.begin() as session:
            channel, receipt = locked(session, identity)
            if receipt is None:
                return False
            if not confirmed(session, identity, settings):
                raise ValueError('Execution state changed')
            archive_copies(session, store, channel)
            validate(receipt.manifest, channel)
            cleanup_files.erase(store, receipt.manifest, namespaces=('domestic-studio',))
            # Serialize the short metadata update only, after all storage I/O.
            lock_admission(session)
            state = session.get(Workspace, (channel.owner_id, channel.workspace))
            if state is None:
                raise ValueError('Conversation workspace missing')
            state.version += 1
            erase_records(session, identity)
            receipt.status, receipt.error, receipt.manifest = 'deleted', None, {}
        return True
    except Exception:
        with factory.begin() as session:
            _, receipt = locked(session, identity)
            if receipt:
                receipt.status, receipt.error = 'delete_failed', '会话清理未完成，请重试或联系管理员'
        return False


def cleanup_once(factory, store=None):
    with factory() as session:
        identities = session.scalars(select(ConversationDeletion.conversation_id)
            .where(ConversationDeletion.status == 'deleting').order_by(ConversationDeletion.created_at).limit(5)).all()
    return sum(process(factory, store or get_store(), identity) for identity in identities)
