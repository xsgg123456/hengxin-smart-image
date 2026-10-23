"""Evidence-bound operator repair of missed native images; never invoke the CLI."""
import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid5
from sqlalchemy import select
from app.core.config import get_settings
from app.execution.diagnostics import _safe_read, _unique_object
from app.execution.events import MAX_EVENTS_BYTES, parse_events
from app.execution.final_delivery import _local_file
from app.execution.output_collector import _checked, _root
from app.modules.files.validation import MAX_UPLOAD_BYTES, validate_image
from app.overseas.db import require_overseas_context
from app.overseas.auth.models import Member
from app.overseas.tasks.models import Task, TaskDeletion, ExecutionObject
from app.overseas.tasks.service import lock_actor
from app.overseas.execution import claims
from app.overseas.execution.models import ACTIVE, Job, JobOutbox
from app.overseas.execution.queue import lock_gate
from app.overseas.execution.events import record
from app.overseas.management.models import Audit
from app.storage.minio_store import get_store
from .models import Turn, Conversation, Picture
from .delivery import references, collect_delivery
from .recovery import require


def _locked(session, turn_id, actor_id):
    actor = session.get(Member, actor_id)
    require(actor is not None, 'Maintenance actor missing')
    lock_actor(session, actor, 'settings.manage')
    turn = session.get(Turn, turn_id)
    require(turn is not None, 'Turn missing')
    task = session.scalar(select(Task).where(Task.id == turn.task_id).with_for_update())
    require(task and task.workflow == 'studio' and task.status == 'studio', 'Task not eligible')
    require(not session.get(TaskDeletion, task.id), 'Task deletion exists')
    require(lock_gate(session).paused, 'Pause execution before image recovery')
    job = claims.locked_job(session, turn.job_id, gate=False)
    require(job and job.task_id == task.id and job.kind == 'studio', 'Job ownership mismatch')
    channel = session.get(Conversation, turn.conversation_id)
    require(channel and channel.task_id == task.id, 'Conversation ownership mismatch')
    if not list(references(turn.reply or '')):
        turns = session.scalars(select(Turn.id).where(Turn.conversation_id == channel.id).limit(2)).all()
        require(turns == [turn.id], 'Native-only recovery requires a single business turn')
    require(isinstance(job.payload, dict) and job.payload.get('turnId') == str(turn.id)
            and job.payload.get('conversationId') == str(channel.id), 'Payload ownership mismatch')
    require(job.status == 'succeeded' and job.process_exited and not job.cancel_requested
            and job.completed_at is not None and job.execution_count > 0
            and job.lease_until is None and turn.dispatched, 'Job not eligible')
    require(not session.scalar(select(Job.id).where(Job.task_id == task.id,
            Job.status.in_(('queued', *ACTIVE)))), 'Task has pending execution')
    outbox = session.get(JobOutbox, job.id)
    require(outbox and outbox.completed_at is not None, 'Dispatch not closed')
    return task, turn, channel, job


def _evidence(turn, channel, job, digest):
    from .native_images import read_history
    base = Path(get_settings().codex_execution_root)
    workspace = _checked(base / 'studio' / str(channel.id), base)
    home = _checked(workspace / 'home' / '.codex', base)
    control = _checked(workspace / 'control' / str(turn.id), base)
    path = _checked(control / 'events.jsonl', base)
    raw = _safe_read(path, MAX_EVENTS_BYTES, allow_windows_fallback=True)
    require(sha256(raw).hexdigest() == digest, 'Event checksum mismatch')
    receipt = json.loads(_safe_read(_checked(control / 'exit.json', base), 4096,
                                  allow_windows_fallback=True), object_pairs_hook=_unique_object)
    require(isinstance(receipt, dict) and type(receipt.get('exit_code')) is int
            and receipt['exit_code'] == 0 and receipt.get('reason') is None,
            'CLI did not exit successfully')
    summary = parse_events(path, channel.session_id)
    require(not summary.error and summary.turn_completed and bool(summary.final_text)
            and summary.session_id == channel.session_id == turn.event_session_id,
            'Completion or session mismatch')
    require(not turn.event_invalid and turn.reply == summary.final_text
            and turn.event_offset == len(raw), 'Stored reply or cursor mismatch')
    require(isinstance(job.result, dict) and job.result.get('reply') == turn.reply
            and job.result.get('sessionId') == channel.session_id
            and isinstance(job.result.get('pictures'), list), 'Stored result mismatch')
    links = list(references(summary.final_text))
    if not links:
        # Empty cursor intentionally requires exactly one complete native turn.
        workspace_view = SimpleNamespace(home=workspace / 'home', work=workspace / 'work',
            baseline={}, native_cursor={}, delivered_images=set())
        outputs, warnings = collect_delivery(workspace_view, summary)
        prefix = '/home/runner/.codex/generated_images/' + channel.session_id + '/'
        require(outputs and not warnings and all(path.startswith(prefix) for path, _ in outputs),
                'No unambiguous native-only delivery evidence')
        require(_safe_read(path, MAX_EVENTS_BYTES, allow_windows_fallback=True) == raw, 'Events changed')
        return dict(outputs)
    require(bool(links) and all(logical is not None for _, logical in links),
            'No complete formal image references')
    proofs = read_history(workspace / 'home', channel.session_id, {logical for _, logical in links})
    root = _root(home, channel.session_id)
    prefix = '/home/runner/.codex/generated_images/' + channel.session_id + '/'
    images = {}
    for target, logical in links:
        require(logical.startswith(prefix) and logical in proofs, 'Native image proof missing')
        file, _ = _local_file(logical, workspace / 'work', home, root, known_files={})
        data = _safe_read(file, MAX_UPLOAD_BYTES, allow_windows_fallback=True)
        image = validate_image(SimpleNamespace(file=BytesIO(data), filename=file.name, content_type=None))
        require(image.checksum == proofs[logical], 'Native image checksum mismatch')
        # Canonical decoded native path makes sandbox: aliases idempotent too.
        images[logical] = image
    require(_safe_read(path, MAX_EVENTS_BYTES, allow_windows_fallback=True) == raw, 'Events changed')
    return images


def _existing(session, task, channel, images):
    rows = session.scalars(select(Picture).join(Turn, Turn.id == Picture.turn_id).where(
        Picture.task_id == task.id, Turn.task_id == task.id, Turn.conversation_id == channel.id)).all()
    found = {}
    for path, image in images.items():
        matches = [row for row in rows if (row.source_path or '').removeprefix('sandbox:') == path
                   and row.checksum == image.checksum]
        require(len(matches) <= 1, 'Duplicate existing pictures')
        if matches:
            found[path] = matches[0]
    return found


def _row(turn, path, image):
    identity = uuid5(turn.id, path + '\n' + image.checksum)
    extension = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}[image.content_type]
    return dict(id=str(identity), name=f'{identity}{extension}', bucket=get_settings().minio_bucket,
                object_key=f'studio/pictures/{turn.task_id}/{identity}', content_type=image.content_type,
                size_bytes=len(image.data), checksum=image.checksum, width=image.width,
                height=image.height, source_path=path)


def recover(factory, turn_id, actor_id, expected_sha256, *, apply=False, store=None):
    """Dry-run by default. Pause the gate and let all task executions close first."""
    require_overseas_context()
    turn_id, actor_id = UUID(str(turn_id)), UUID(str(actor_id))
    with factory.begin() as session:
        task, turn, channel, job = _locked(session, turn_id, actor_id)
        previous = session.scalar(select(Audit).where(Audit.action == 'studio.image_recovery',
                                                     Audit.target == str(job.id)))
        require(not previous or previous.after.get('eventSha256') == expected_sha256, 'Evidence changed')
        images = _evidence(turn, channel, job, expected_sha256)
        found = _existing(session, task, channel, images)
        report = dict(status='already_recovered' if len(found) == len(images) else 'eligible',
                      jobId=str(job.id), eventSha256=expected_sha256, pictureCount=len(images),
                      paths=list(images), checksums=[image.checksum for image in images.values()])
        if not apply or len(found) == len(images):
            return report
        rows = {path: _row(turn, path, image) for path, image in images.items() if path not in found}
        for row in rows.values():
            ledger = session.scalar(select(ExecutionObject).where(
                ExecutionObject.object_key == row['object_key']))
            if ledger:
                require(ledger.task_id == task.id and ledger.job_id == job.id
                        and ledger.bucket == row['bucket'], 'Object ledger ownership mismatch')
            else:
                session.add(ExecutionObject(task_id=task.id, job_id=job.id,
                    bucket=row['bucket'], object_key=row['object_key']))
    # Separate transaction preserves the ledger if storage fails or this process dies.
    with factory.begin() as session:
        task, turn, channel, job = _locked(session, turn_id, actor_id)
        current = _evidence(turn, channel, job, expected_sha256)
        require({key: image.checksum for key, image in current.items()} ==
                {key: image.checksum for key, image in images.items()}, 'Image evidence changed')
        found = _existing(session, task, channel, current)
        if len(found) == len(current):
            return {**report, 'status': 'already_recovered'}
        storage = store if store is not None else get_store()
        outputs = list(job.result['pictures'])
        added = []
        for path, image in current.items():
            if path in found:
                continue
            require(path in rows, 'Recovery snapshot changed')
            row = rows[path]
            ledger = session.scalar(select(ExecutionObject).where(
                ExecutionObject.object_key == row['object_key']))
            require(ledger and ledger.task_id == task.id and ledger.job_id == job.id
                    and ledger.bucket == row['bucket'], 'Object ledger missing')
            storage.put(SimpleNamespace(**row), image.data)
            session.add(Picture(**{**row, 'id': UUID(row['id'])}, task_id=task.id, turn_id=turn.id))
            outputs.append(row)
            added.append(row['id'])
        before = dict(deliveryError=turn.delivery_error, pictureCount=len(job.result['pictures']),
                      version=job.version, executionCount=job.execution_count,
                      completedAt=job.completed_at.isoformat())
        turn.delivery_error = None
        job.result = {**job.result, 'pictures': outputs, 'deliveryError': None}
        job.version += 1
        record(session, job)
        report = {**report, 'status': 'succeeded', 'addedPictureIds': added}
        session.add(Audit(actor_id=actor_id, action='studio.image_recovery', target=str(job.id),
                          before=before, after={**report, 'version': job.version}))
        return report
