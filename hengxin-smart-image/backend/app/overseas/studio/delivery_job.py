"""Durable per-image collection. A failed save never starts another model run."""
from datetime import datetime, timedelta
import logging
from types import SimpleNamespace
from uuid import UUID
from sqlalchemy import select

from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.overseas.execution import claims
from app.overseas.tasks.models import Task, TaskDeletion, ExecutionObject
from .models import Conversation, ConversationDeletion, Turn, Picture
from . import context_fs as fs, delivery_context as context, delivery_snapshot as snapshots

log = logging.getLogger(__name__)


class OwnershipLost(ValueError):
    pass


def guarded(session, job_id, token):
    from app.overseas.execution.models import Job
    task_id = session.scalar(select(Job.task_id).where(Job.id == job_id))
    task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
    job = claims.locked_job(session, job_id)
    if not task or not claims.valid(job, token) or not job.process_exited:
        raise OwnershipLost('Delivery ownership lost')
    turn = session.get(Turn, UUID(job.payload['turnId']))
    if (not turn or turn.job_id != job.id or turn.task_id != task.id
            or str(turn.conversation_id) != job.payload['conversationId']
            or session.get(TaskDeletion, task.id)
            or session.get(ConversationDeletion, turn.conversation_id)):
        raise OwnershipLost('Delivery was cancelled or deleted')
    return job, turn


def progress(factory, job_id, token, summary, state, expected, order=()):
    with factory.begin() as session:
        job, turn = guarded(session, job_id, token)
        channel = session.get(Conversation, turn.conversation_id)
        if not channel or channel.session_id not in (None, summary.session_id):
            raise OwnershipLost('Delivery session mismatch')
        channel.session_id = summary.session_id
        turn.reply, turn.delivery_error = summary.final_text, None
        saved = list(session.scalars(select(Picture.id).where(Picture.turn_id == turn.id)))
        result = dict(job.result or {})
        result.update(reply=summary.final_text, sessionId=summary.session_id,
            deliveryStatus=dict(state=state, expected=expected, saved=len(saved)))
        if order:
            result['deliveryOrder'] = list(order)
        if job.result != result:
            job.result = result
            job.version += 1
            from app.overseas.execution.events import record
            record(session, job)
        return len(saved)


def row_data(job, target, image, item):
    extension = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[image.content_type]
    identity = UUID(item['pictureId'])
    return dict(id=identity, task_id=job.task_id, turn_id=UUID(job.payload['turnId']),
        name=f'{identity}{extension}', bucket=get_settings().minio_bucket,
        object_key=f'studio/pictures/{job.task_id}/{identity}', content_type=image.content_type,
        size_bytes=len(image.data), checksum=image.checksum, width=image.width,
        height=image.height, source_path=target)


def upload(factory, job, token, store, data, image):
    with factory.begin() as session:
        guarded(session, job.id, token)
        existing = session.get(Picture, data['id'])
        if existing:
            if any(getattr(existing, key) != data[key] for key in
                   ('task_id', 'turn_id', 'object_key', 'checksum', 'source_path')):
                raise ValueError('Conflicting delivery image identity')
            return
        ledger = session.scalar(select(ExecutionObject).where(
            ExecutionObject.bucket == data['bucket'], ExecutionObject.object_key == data['object_key']))
        if ledger and (ledger.job_id != job.id or ledger.task_id != job.task_id):
            raise OwnershipLost('Conflicting delivery object ownership')
        if ledger is None:
            session.add(ExecutionObject(task_id=job.task_id, job_id=job.id,
                bucket=data['bucket'], object_key=data['object_key']))
    # The object ledger commits before upload. Stable keys and immutable bytes
    # make an unknown upload outcome safe to inspect and retry.
    with factory.begin() as session:
        guarded(session, job.id, token)
        if session.get(Picture, data['id']):
            return
        from .files import read
        record = SimpleNamespace(**data)
        try:
            read(store, record)
        except Exception:
            store.put(record, image.data)
            read(store, record)
        guarded(session, job.id, token)
        session.add(Picture(**data))


def defer(factory, job_id, token):
    with factory.begin() as session:
        job, _ = guarded(session, job_id, token)
        result = dict(job.result or {})
        attempts = int(result.get('deliveryAttempts', 0)) + 1
        result['deliveryAttempts'] = attempts
        result['deliveryRetryAt'] = (utcnow() + timedelta(seconds=min(300, 5 * 2 ** min(attempts, 6)))).isoformat()
        job.result = result
        job.status, job.error = 'collecting', None
        job.version += 1
        from app.overseas.execution.events import record
        record(session, job)
        # Collection remains active, protecting work from subsequent turns and
        # cleanup. Reconciliation takes a new lease; the old token cannot publish.
        job.lease_until = utcnow()


def deliver(factory, job, token, workspace, summary, store):
    from .delivery import enumerate_delivery, collect_reference
    progress(factory, job.id, token, summary, 'capturing', None)
    root = workspace.control / 'delivery'
    with factory.begin() as session:
        guarded(session, job.id, token)
        context.close_native(workspace, summary.session_id)
        manifest = snapshots.load(root)
        if manifest is None:
            selection_path = workspace.control / 'delivery-selection.json'
            if selection_path.exists():
                selection = fs.load(selection_path)
            else:
                references, proven, warnings = enumerate_delivery(workspace, summary)
                if not references and warnings:
                    raise ValueError('Final native image presentation is not yet readable')
                selection = dict(references=references, proven=proven, issues=warnings)
                fs.save(selection_path, selection)
            manifest = snapshots.begin(root, context.identity(job), summary.final_text,
                                       summary.session_id, [row[0] for row in selection['references']])
        else:
            if manifest['identity'] != {**context.identity(job), 'sessionId': summary.session_id}:
                raise OwnershipLost('Frozen delivery does not belong to this invocation')
            if manifest['finalText'] != summary.final_text:
                raise ValueError('Frozen final reply changed')
    selection = fs.load(workspace.control / 'delivery-selection.json')
    expected = len(manifest['targets']) + len(selection.get('issues', []))
    for item in manifest['items']:
        if item['status'] == 'captured':
            continue
        try:
            with factory.begin() as session:
                guarded(session, job.id, token)
                selection = fs.load(workspace.control / 'delivery-selection.json')
                target = item['target']
                logical = next(row[1] for row in selection['references'] if row[0] == target)
                image = collect_reference(workspace, summary, target, logical, selection['proven'])
                snapshots.capture(root, target, image)
        except OwnershipLost:
            raise
        except Exception:
            log.warning('Studio delivery capture pending job=%s item=%s', job.id, item['order'])
    manifest = snapshots.load(root)
    order = [item['pictureId'] for item in manifest['items'] if item['status'] == 'captured']
    progress(factory, job.id, token, summary, 'saving' if manifest['ready'] else 'capturing', expected, order)
    for target, image, item in snapshots.images(root, captured_only=True):
        try:
            upload(factory, job, token, store, row_data(job, target, image, item), image)
            progress(factory, job.id, token, summary, 'saving', expected, order)
        except OwnershipLost:
            raise
        except Exception:
            log.warning('Studio delivery upload pending job=%s item=%s', job.id, item['order'])
    saved = progress(factory, job.id, token, summary, 'saving', expected, order)
    if manifest['ready'] and saved == expected:
        with factory.begin() as session:
            current, _ = guarded(session, job.id, token)
            result = dict(current.result)
            result['deliveryStatus'] = dict(state='complete', expected=expected, saved=saved)
            claims.end(session, current, 'succeeded', result=result)
            if result.get('deliveryOriginalCompletedAt'):
                current.completed_at = datetime.fromisoformat(result['deliveryOriginalCompletedAt'])
                from app.overseas.execution.models import JobOutbox
                outbox = session.get(JobOutbox, current.id)
                if outbox:
                    outbox.completed_at = current.completed_at
        return True
    defer(factory, job.id, token)
    return False
