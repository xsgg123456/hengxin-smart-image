"""Native maintenance erases only proven conversation-owned resources."""
from pathlib import Path, PurePosixPath
from sqlalchemy import delete, select
from app.core.config import get_settings
from app.overseas.db import require_overseas_context
from app.overseas.tasks.models import Task, TaskDeletion, ExecutionObject
from app.overseas.tasks import cleanup_files, cleanup_process
from app.overseas.materials.models import Material
from app.overseas.pictures.models import PictureVersion
from app.overseas.execution.models import Job, JobOutbox, ExecutionEvent, TERMINAL
from app.overseas.archives.models import Archive, ArchiveAsset, ArchiveDeletion
from app.overseas.archives.snapshot import protect
from app.storage.minio_store import get_store
from .models import Conversation, ConversationDeletion, Turn, Upload, Picture, OutputFile, Transcript, MaterialVisibility


def jobs_for(session, identity):
    return session.scalars(select(Job).join(Turn, Turn.job_id == Job.id)
        .where(Turn.conversation_id == identity)).all()


def confirmed(session, identity):
    for job in jobs_for(session, identity):
        if job.status not in TERMINAL or (job.worker_node and job.worker_node != get_settings().worker_node_name):
            return False
        if job.execution_count and not job.process_exited:
            return False
        if job.process_id:
            if not all((job.process_boot, job.process_started)) or cleanup_process.group_alive(job):
                return False
    return True


def inventory(session, row, store):
    turns = select(Turn.id).where(Turn.conversation_id == row.id)
    jobs = select(Turn.job_id).where(Turn.conversation_id == row.id)
    outside = session.execute(select(Turn, Job).join(Job, Turn.job_id == Job.id).where(
        Turn.task_id == row.task_id, Turn.conversation_id != row.id)).all()
    referenced = {value for turn, _ in outside for value in turn.reference_ids}
    frozen = {(item['bucket'], item['object_key']) for _, job in outside
              for item in job.payload.get('inputs', [])}
    pictures = list(session.scalars(select(Picture).where(Picture.task_id == row.task_id,
        Picture.turn_id.in_(turns) | Picture.turn_id.is_(None))))
    retained = [picture for picture in pictures if str(picture.id) in referenced
                or (picture.bucket, picture.object_key) in frozen]
    protected = {(picture.bucket, picture.object_key) for picture in retained}
    erased = [picture for picture in pictures if picture not in retained]
    sources = list(session.scalars(select(Upload).where(Upload.conversation_id == row.id)))
    sources += list(session.scalars(select(OutputFile).where(OutputFile.turn_id.in_(turns))))
    sources += erased
    sources += [item for item in session.scalars(select(ExecutionObject).where(ExecutionObject.job_id.in_(jobs)))
                if (item.bucket, item.object_key) not in protected]
    objects = {(item.bucket, item.object_key) for item in sources}
    prefix = f'studio/uploads/{row.task_id}/{row.id}/'
    for bucket in {get_settings().minio_bucket, *(bucket for bucket, _ in objects)}:
        for key in store.keys(bucket, prefix):
            if not key.startswith(prefix):
                raise ValueError('Storage listing escaped conversation namespace')
            objects.add((bucket, key))
    for bucket, key in objects:
        path = PurePosixPath(key)
        if (path.is_absolute() or '..' in path.parts or '\\' in key or ':' in key
                or not path.parts or path.parts[0] not in ('studio', 'pictures')):
            raise ValueError('Invalid conversation object ownership')
        if session.scalar(select(ArchiveAsset.id).where(ArchiveAsset.bucket == bucket,
                ArchiveAsset.object_key == key).limit(1)):
            raise ValueError('Archive bytes must remain independent')
        if session.scalar(select(Material.id).where(Material.bucket == bucket,
                Material.object_key == key).limit(1)):
            raise ValueError('Task material cannot be erased')
        if session.scalar(select(PictureVersion.id).where(PictureVersion.bucket == bucket,
                PictureVersion.object_key == key).limit(1)):
            raise ValueError('Legacy picture cannot be erased')
        for model, condition in (
            (Upload, (Upload.conversation_id.is_(None) | (Upload.conversation_id != row.id))),
            (Picture, Picture.id.not_in([picture.id for picture in erased])),
            (ExecutionObject, ExecutionObject.job_id.not_in(jobs)),
            (OutputFile, OutputFile.turn_id.not_in(turns)),
        ):
            if session.scalar(select(model.id).where(model.bucket == bucket,
                    model.object_key == key, condition).limit(1)):
                raise ValueError('Shared conversation object')
    manifest = dict(objects=[dict(bucket=bucket, object_key=key) for bucket, key in sorted(objects)],
        directories=['studio/' + str(row.id)], root=str(Path(get_settings().codex_execution_root).absolute()),
        picture_ids=[str(picture.id) for picture in erased],
        retained_picture_ids=[str(picture.id) for picture in retained if picture.turn_id is not None])
    cleanup_files.validate_directories(manifest)
    return manifest


def erase_records(session, identity, manifest):
    from uuid import UUID
    for value in manifest['retained_picture_ids']:
        picture = session.get(Picture, UUID(value))
        picture.origin_turn_id, picture.turn_id = picture.turn_id, None
    session.flush()
    # Materialize IDs before deleting turns, which own the job relationship.
    turns = list(session.scalars(select(Turn.id).where(Turn.conversation_id == identity)))
    jobs = list(session.scalars(select(Turn.job_id).where(Turn.conversation_id == identity)))
    for model, condition in (
        (Transcript, Transcript.turn_id.in_(turns)), (Picture, Picture.id.in_([UUID(value) for value in manifest['picture_ids']])),
        (Upload, Upload.conversation_id == identity), (OutputFile, OutputFile.turn_id.in_(turns)),
        (Turn, Turn.id.in_(turns)),
        (MaterialVisibility, MaterialVisibility.scope == str(identity)),
        (ExecutionObject, ExecutionObject.job_id.in_(jobs)),
        (ExecutionEvent, ExecutionEvent.job_id.in_(jobs)), (JobOutbox, JobOutbox.job_id.in_(jobs)),
        (Job, Job.id.in_(jobs)), (Conversation, Conversation.id == identity),
    ):
        session.execute(delete(model).where(condition).execution_options(synchronize_session=False))


def locked(session, identity):
    task_id = session.scalar(select(ConversationDeletion.task_id).where(ConversationDeletion.conversation_id == identity))
    task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
    receipt = session.scalar(select(ConversationDeletion).where(ConversationDeletion.conversation_id == identity)
        .with_for_update(skip_locked=True).execution_options(populate_existing=True))
    return task, receipt


def process(factory, store, identity):
    try:
        with factory.begin() as session:
            task, receipt = locked(session, identity)
            if not task or not receipt or receipt.status != 'deleting' or session.get(TaskDeletion, task.id):
                return False
            if not confirmed(session, identity):
                raise ValueError('Process exit not verified')
            row = session.get(Conversation, identity)
            if not row or row.task_id != task.id:
                raise ValueError('Missing conversation before erasure')
            for record in session.scalars(select(Archive).where(Archive.task_id == task.id)):
                if session.get(ArchiveDeletion, record.id):
                    raise ValueError('Archive deletion in progress')
                protect(session, store, record, task)
            if not receipt.manifest:
                receipt.manifest = inventory(session, row, store)
        # Commit independent archive copies and durable inventory before erasing.
        with factory.begin() as session:
            task, receipt = locked(session, identity)
            if not task or not receipt or receipt.status != 'deleting' or session.get(TaskDeletion, task.id):
                return False
            if not confirmed(session, identity):
                raise ValueError('Process state changed')
            cleanup_files.erase(store, receipt.manifest)
            erase_records(session, identity, receipt.manifest)
            receipt.status, receipt.error, receipt.manifest = 'deleted', None, {}
        return True
    except Exception:
        with factory.begin() as session:
            _, receipt = locked(session, identity)
            if receipt and receipt.status != 'deleted':
                receipt.status = 'delete_failed'
                receipt.error = '会话清理未完成，已保留归档；请检查文件或执行状态后重试'
        return False


def cleanup_once(factory, store=None):
    require_overseas_context()
    with factory() as session:
        identities = session.scalars(select(ConversationDeletion.conversation_id).where(
            ConversationDeletion.status == 'deleting').order_by(ConversationDeletion.created_at).limit(20)).all()
    return sum(process(factory, store or get_store(), identity) for identity in identities)
