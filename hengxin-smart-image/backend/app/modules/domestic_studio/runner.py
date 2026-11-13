"""Domestic Codex execution with durable dispatch and delivery fences."""
import subprocess
from pathlib import Path
from uuid import UUID

from app.capacity.admission import covered, published
from app.core.config import get_settings
from app.execution.managed_credentials import sync_credentials
from app.execution.process import execute
from app.execution.workspace import sandbox_command
from app.modules.api_image_edits.execution_policy import CLI_MODEL, CLI_REASONING_EFFORT
from app.storage.minio_store import get_store
from app.worker.leases import heartbeat, lease_active
from app.worker.leases import TERMINAL
from app.models import Job
from app.overseas.studio.delivery_context import close_native
from . import delivery_capture, delivery_context, execution_workspace, output_store, runtime
from .bindings import lock_admission
from .management_router import get_catalog
from .transcript import Monitor


def settle(factory, job_id, token, status, error=None, reply=None, *, stopped=False):
    """Only the still-owned process may publish a terminal state."""
    with factory.begin() as session:
        lock_admission(session)
        state, channel, turn, job = runtime.locked(session, job_id)
        if not job or job.claim_token != token or job.status != 'running':
            return False
        if not lease_active(job):
            status, error = 'uncertain', '执行状态待核实，禁止自动重试'
        elif turn.cancel_requested:
            status = 'cancelled' if stopped else 'uncertain'
            error = None if stopped else '正在核实原执行进程'
        if reply is not None and status in ('succeeded', 'partial'):
            turn.reply = reply
        runtime.finish(session, state, channel, turn, job, status, error)
        if status != 'uncertain':
            published(session, turn.id)
        return True


def record_start(factory, job_id, token, settings, pid, boot, birth):
    with factory.begin() as session:
        lock_admission(session)
        state, channel, turn, job = runtime.locked(session, job_id)
        if not job or not runtime.valid(turn, job, token):
            raise ValueError('Domestic Studio execution ownership lost')
        turn.process_identity = {'pid': pid, 'boot': boot, 'birth': birth, 'node': settings.worker_node_name}
        runtime.changed(state, channel, turn)


def dispatch_fence(factory, job_id, token):
    with factory.begin() as session:
        lock_admission(session)
        state, channel, turn, job = runtime.locked(session, job_id)
        if not job or not runtime.valid(turn, job, token):
            return False
        if not covered(session, turn.id, 'cli', turn.id, 20 * 1024 * 1024):
            raise ValueError('Domestic Studio capacity reservation missing')
        turn.dispatched = True
        runtime.changed(state, channel, turn)
        return True


def deliver(factory, job_id, token, workspace, owner, store, settings):
    summary = delivery_context.success(workspace)
    if not summary.final_text:
        raise ValueError('Domestic Studio final reply missing')
    close_native(workspace, summary.session_id)
    manifest, files, issues = delivery_capture.capture(workspace, summary, owner)
    for target, data, item in files:
        try:
            output_store.save(factory, job_id, token, store, settings.minio_bucket, target, data, item)
        except Exception:
            issues.append('部分文件保存失败，请保留会话并联系管理员处理')
        finally:
            del data
    if issues or not manifest['ready']:
        settle(factory, job_id, token, 'partial', '部分文件未保存，可通过“取回文件”选择尚存原件，无需重新生成',
               reply=summary.final_text, stopped=True)
        return False
    return settle(factory, job_id, token, 'succeeded', reply=summary.final_text, stopped=True)


def run_turn(job_id, factory, store=None, catalog=None):
    settings = get_settings()
    job_id = UUID(str(job_id))
    with factory() as session:
        job = session.get(Job, job_id)
        if not job or job.status in TERMINAL:
            return
    from . import recovery
    if recovery.handle(factory, job_id, settings, store):
        return
    if not settings.enable_codex_executor:
        return
    token = runtime.claim(factory, job_id)
    if not token:
        return
    spawning = exited = completed = False
    try:
        store, catalog = store or get_store(), catalog or get_catalog()
        with heartbeat(factory, job_id, token):
            version = subprocess.run([settings.codex_binary, '--version'], capture_output=True, text=True, timeout=10)
            if version.returncode or version.stdout.strip() != f'codex-cli {settings.codex_version}':
                raise ValueError('CLI version mismatch')
            workspace, payload = execution_workspace.prepare(factory, job_id, settings, catalog, store)
            sync_credentials(Path(settings.codex_auth_file), workspace.home, payload['timeoutSeconds'],
                broker_socket=settings.codex_auth_broker_socket or None,
                control=workspace.control.parent, require_existing=bool(workspace.previous_session))
            with factory.begin() as session:
                lock_admission(session)
                _, channel, turn, job = runtime.locked(session, job_id)
                if not job or not runtime.valid(turn, job, token):
                    settle_needed = True
                else:
                    settle_needed = False
                    owner = delivery_context.identity(job.id, channel.owner_id, channel.id, turn.id)
            if settle_needed:
                settle(factory, job_id, token, 'cancelled', stopped=True)
                return
            delivery_context.remember(workspace, owner)
            args = ['exec', '--model', CLI_MODEL, '-c', f'model_reasoning_effort="{CLI_REASONING_EFFORT}"',
                    '--sandbox', 'workspace-write']
            args += (['resume', '--skip-git-repo-check', '--json', workspace.previous_session]
                     if workspace.previous_session else ['--skip-git-repo-check', '--json'])
            command = sandbox_command(workspace, settings.codex_binary, args + ['-'], settings.codex_bwrap_binary)
            monitor = Monitor(factory, job_id, token, workspace.control)
            if monitor() or not dispatch_fence(factory, job_id, token):
                settle(factory, job_id, token, 'cancelled', stopped=True)
                return
            spawning = True
            receipt = execute(command, execution_workspace.prompt(workspace, payload), workspace.control,
                payload['timeoutSeconds'], monitor,
                lambda pid, boot, birth: record_start(factory, job_id, token, settings, pid, boot, birth))
            exited = True
            if monitor.poll(final=True) or receipt.get('reason') or receipt.get('exit_code') != 0:
                settle(factory, job_id, token, 'failed', '本轮执行未完成', stopped=True)
                return
            # success() requires the process exit receipt and complete event stream.
            summary = delivery_context.success(workspace)
            if not summary.final_text:
                raise ValueError('Domestic Studio final reply missing')
            completed = True
            deliver(factory, job_id, token, workspace, owner, store, settings)
    except Exception:
        status = 'uncertain' if (spawning and not exited) or completed else 'failed'
        message = '执行状态待核实，禁止自动重试' if status == 'uncertain' else '执行未完成，请联系管理员检查环境'
        settle(factory, job_id, token, status, message, stopped=exited or not spawning)
