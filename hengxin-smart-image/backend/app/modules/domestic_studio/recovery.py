"""Verify the original worker and process before stopping or re-collecting."""
from datetime import timedelta
from uuid import uuid4

from app.capacity.admission import published
from app.db.timestamps import utcnow
from app.execution.process import same_process
from app.execution.process_group import group_alive
from app.execution.verified_stop import stopped
from app.storage.minio_store import get_store
from app.worker.leases import heartbeat
from . import delivery_context, runtime
from .bindings import lock_admission


def state(factory, job_id):
    with factory.begin() as session:
        lock_admission(session)
        _, channel, turn, job = runtime.locked(session, job_id)
        if not job or job.status != 'uncertain':
            return None
        owner = delivery_context.identity(job.id, channel.owner_id, channel.id, turn.id)
        return owner, dict(turn.process_identity or {}), turn.cancel_requested, turn.recovery_requested, job.claim_token


def stop_uncertain(factory, job_id, settings, process):
    if not stopped(process, settings.worker_node_name):
        return True
    with factory.begin() as session:
        lock_admission(session)
        workspace, channel, turn, job = runtime.locked(session, job_id)
        if (job and job.status == 'uncertain' and turn.cancel_requested
                and turn.process_identity == process):
            runtime.finish(session, workspace, channel, turn, job, 'cancelled', '原执行进程已停止')
            published(session, turn.id)
    return True


def recover(factory, job_id, settings, store, owner, process, old_token):
    if process.get('node') != settings.worker_node_name:
        return True
    try:
        if (same_process(process['pid'], process['boot'], process['birth'])
                or group_alive(process['pid'], process['boot'])):
            return True
        workspace = delivery_context.restore(settings.codex_execution_root, owner)
        delivery_context.success(workspace)
    except (OSError, ValueError, KeyError, TypeError):
        return True  # Missing proof never authorizes a new model invocation.
    with factory.begin() as session:
        lock_admission(session)
        state, channel, turn, job = runtime.locked(session, job_id)
        if (not job or job.status != 'uncertain' or job.claim_token != old_token
                or not turn.recovery_requested or turn.cancel_requested or turn.process_identity != process):
            return True
        job.claim_token = token = uuid4()
        job.status, job.lease_until, job.error = 'running', utcnow() + timedelta(seconds=settings.job_lease_seconds), None
        turn.recovery_requested, turn.error = False, None
        runtime.changed(state, channel, turn)
    from . import runner
    try:
        with heartbeat(factory, job_id, token):
            runner.deliver(factory, job_id, token, workspace, owner, store or get_store(), settings)
    except Exception:
        runner.settle(factory, job_id, token, 'uncertain', '文件收取未完成，请重试收取', stopped=True)
    return True


def handle(factory, job_id, settings, store=None):
    current = state(factory, job_id)
    if current is None:
        return False
    owner, process, cancel, requested, old_token = current
    if cancel:
        return stop_uncertain(factory, job_id, settings, process)
    if requested:
        return recover(factory, job_id, settings, store, owner, process, old_token)
    return True  # Uncertain jobs never pass through the normal claim path.
