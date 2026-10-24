"""Authorized historical repair through the same durable collector; no model calls."""
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4
from sqlalchemy import select

from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.overseas.db import require_overseas_context
from app.overseas.execution.events import record
from app.overseas.management.models import Audit
from app.overseas.tasks.cleanup_process import group_alive
from app.storage.minio_store import get_store
from . import context_fs as fs, delivery_context as context
from .delivery import enumerate_delivery, collect_reference
from .delivery_job import deliver
from .image_recovery import _locked
from .models import Picture, OutputFile, ConversationDeletion
from .recovery import require


def evidence(turn, channel, job, expected_sha256, expected_checksums):
    root = Path(get_settings().codex_execution_root).absolute() / 'studio' / str(channel.id)
    control = fs.checked(root / 'control' / str(turn.id), directory=True)
    raw = fs.load(control / 'exit.json')
    require(raw.get('exit_code') == 0 and not raw.get('reason'), 'Original process was not successful')
    require(fs.digest(control / 'events.jsonl')[0] == expected_sha256, 'Original event digest changed')
    from .completion import read
    summary = read(control / 'events.jsonl', channel.session_id)
    require(summary.turn_completed and not summary.error and summary.final_text == turn.reply
            and summary.session_id == channel.session_id, 'Original final response changed')
    persistent = (root / 'persistent' / 'work').exists()
    workspace = SimpleNamespace(home=fs.checked(root / 'home', directory=True),
        work=fs.checked(root / 'persistent' / 'work' if persistent else root / 'rounds' / str(turn.id), directory=True),
        control=control, persistent=persistent, previous_session=channel.session_id,
        baseline={}, native_cursor=None, delivered_images=set())
    references, proven, warnings = enumerate_delivery(workspace, summary)
    require(references and not warnings, 'Original final images are not readable')
    checksums = {}
    for target, logical in references:
        image = collect_reference(workspace, summary, target, logical, proven)
        checksums[target] = image.checksum
    require(checksums == expected_checksums, 'Original image bytes or selection changed')
    return workspace, summary, checksums, raw


def repair(factory, turn_id, actor_id, expected_sha256, expected_checksums, *, apply=False, store=None):
    """Gate must be paused and task drained; dry-run verifies exact original bytes."""
    require_overseas_context()
    turn_id, actor_id = UUID(str(turn_id)), UUID(str(actor_id))
    with factory.begin() as session:
        task, turn, channel, job = _locked(session, turn_id, actor_id)
        require(not session.get(ConversationDeletion, channel.id), 'Conversation deletion exists')
        require(not job.process_id or not group_alive(job), 'Original process group still active')
        workspace, summary, checksums, receipt = evidence(turn, channel, job, expected_sha256, expected_checksums)
        existing = [row for model in (Picture, OutputFile)
                    for row in session.scalars(select(model).where(model.turn_id == turn.id))]
        found = {row.source_path: row.checksum for row in existing}
        report = dict(jobId=str(job.id), turnId=str(turn.id), expected=len(checksums),
            saved=len(existing), checksums=checksums, eventSha256=expected_sha256,
            status='already_recovered' if found == checksums else 'eligible')
        if not apply or found == checksums:
            return report
        require(not existing, 'Partial legacy records require explicit reconciliation')
        context.remember(job, workspace)
        context.exited(workspace, receipt)
        before = dict(completedAt=job.completed_at.isoformat(), executionCount=job.execution_count,
                      deliveryError=turn.delivery_error, version=job.version)
        job.result = {**(job.result or {}), 'deliveryOriginalCompletedAt': before['completedAt']}
        job.status, job.claim_token = 'collecting', uuid4()
        job.worker_node = get_settings().worker_node_name
        job.lease_until = utcnow() + timedelta(seconds=get_settings().job_lease_seconds)
        job.version += 1
        record(session, job)
        session.add(Audit(actor_id=actor_id, action='studio.delivery_repair', target=str(job.id),
                          before=before, after={**report, 'status': 'collecting'}))
        session.flush()
        session.expunge(job)
    from app.overseas.execution.runner import heartbeat
    with heartbeat(factory, job.id, job.claim_token, get_settings()):
        completed = deliver(factory, job, job.claim_token, workspace, summary, store or get_store())
    with factory.begin() as session:
        audit = session.scalar(select(Audit).where(Audit.action == 'studio.delivery_repair',
            Audit.target == str(job.id)).order_by(Audit.created_at.desc()).limit(1))
        if audit:
            audit.after = {**audit.after, 'status': 'succeeded' if completed else 'partial'}
    return {**report, 'status': 'succeeded' if completed else 'partial'}
