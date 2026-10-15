"""Isolated overseas CLI, with durable ownership and verified exit fencing."""
import shutil
import logging
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.overseas.db import require_overseas_context
from app.execution.events import parse_events
from app.execution.process import execute
from app.execution.workspace import prepare_workspace, sandbox_command
from . import claims, materials, protocols
from .events import record
from .models import ACTIVE, Job


def resources_available(settings):
    root = Path(settings.codex_execution_root).resolve()
    while not root.exists() and root != root.parent:
        root = root.parent
    try:
        return shutil.disk_usage(root).free >= 512 * 1024 * 1024
    except OSError:
        return False


@contextmanager
def heartbeat(factory, job_id, token, settings):
    stopped, lost = threading.Event(), threading.Event()
    def beat():
        while not stopped.wait(settings.job_heartbeat_seconds):
            try:
                if claims.renew(factory, job_id, token):
                    continue
            except Exception:
                pass
            lost.set()
            return
    thread = threading.Thread(target=beat, daemon=True)
    thread.start()
    try:
        yield lost
    finally:
        stopped.set()
        thread.join(timeout=2)


def should_stop(factory, job_id, token):
    with factory() as session:
        return not claims.valid(session.get(Job, job_id), token)


def _exit(factory, job_id, token):
    with factory.begin() as session:
        job = claims.locked_job(session, job_id)
        if job and job.claim_token == token and job.status in ACTIVE:
            job.process_exited = True


def _fail(factory, job_id, token, error=True):
    with factory.begin() as session:
        job = claims.locked_job(session, job_id)
        if job and job.claim_token == token and job.status in ACTIVE and job.process_exited:
            claims.end(session, job, 'cancelled' if job.cancel_requested else 'failed', error=error)


def run(factory, job_id):
    require_overseas_context()
    settings = get_settings()
    if not settings.enable_codex_executor or not resources_available(settings):
        return
    job_id = UUID(str(job_id))
    token = claims.claim(factory, job_id, admission=lambda: resources_available(settings))
    if not token:
        return
    spawning, exited = False, False
    handler = workspace = job = None
    failure = True
    try:
        with heartbeat(factory, job_id, token, settings) as lost:
            with factory() as session:
                job = session.get(Job, job_id)
                session.expunge(job)
            handler = protocols.resolve(job.kind)
            version = subprocess.run([settings.codex_binary, '--version'], capture_output=True,
                                     text=True, timeout=10)
            if version.returncode or version.stdout.strip() != f'codex-cli {settings.codex_version}':
                raise ValueError('CLI version mismatch')
            # Separate job homes avoid parallel SKU jobs sharing writable sessions.
            workspace = (handler.workspace(factory, job, token, settings) if hasattr(handler, 'workspace')
                         else prepare_workspace(settings.codex_execution_root, job.id, token,
                                                settings.codex_auth_file))
            materials.prepare(job, workspace)
            prompt = handler.prepare(job, workspace)
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError('Empty protocol prompt')
            args = (handler.arguments(workspace) if hasattr(handler, 'arguments') else
                    ['exec', '--sandbox', 'workspace-write', '--skip-git-repo-check', '--json', '-'])
            command = sandbox_command(workspace, settings.codex_binary, args, settings.codex_bwrap_binary)
            with factory.begin() as session:
                current = claims.locked_job(session, job_id)
                if not claims.valid(current, token) or lost.is_set():
                    raise ValueError('Ownership lost before spawn')
                current.worker_node = settings.worker_node_name

            def started(pid, boot, birth):
                with factory.begin() as session:
                    current = claims.locked_job(session, job_id)
                    if current.claim_token != token:
                        raise ValueError('Ownership changed')
                    current.process_id, current.process_boot, current.process_started = pid, boot, birth

            timeout = job.payload.get('runtime', {}).get('timeoutSeconds', settings.codex_timeout_seconds)
            if type(timeout) is not int or not 10 <= timeout <= 7200:
                raise ValueError('Invalid frozen timeout')
            def monitor():
                if hasattr(handler, 'poll'):
                    handler.poll(factory, job, token, workspace)
                return lost.is_set() or should_stop(factory, job_id, token)

            if hasattr(handler, 'before_execute'):
                handler.before_execute(factory, job, token)
            spawning = True
            receipt = execute(command, prompt, workspace.control, timeout,
                              monitor, started)
            exited = True
            _exit(factory, job_id, token)
            if hasattr(handler, 'final_poll'):
                handler.final_poll(factory, job, token, workspace)
            elif hasattr(handler, 'poll'):
                handler.poll(factory, job, token, workspace)
            summary = parse_events(workspace.control / 'events.jsonl', getattr(workspace, 'previous_session', None))
            if receipt.get('exit_code') != 0 or receipt.get('reason'):
                raise ValueError('CLI did not complete')
            if summary.error or not summary.turn_completed or not summary.session_id:
                failure = summary.error or True
                logging.getLogger(__name__).warning('CLI event validation failed job=%s code=%s',
                                                   job_id, summary.error or 'incomplete_stream')
                raise ValueError('Protocol stream incomplete')
            with factory.begin() as session:
                current = claims.locked_job(session, job_id)
                if not claims.valid(current, token) or lost.is_set():
                    raise ValueError('Ownership lost')
                current.status = 'collecting'
                current.version += 1
                record(session, current)
            from .objects import collecting
            with collecting(factory, job, token):
                result = handler.validate(job, workspace, summary)
            if not isinstance(result, dict) or not result:
                raise ValueError('Protocol did not return validated output')
            if not claims.finish(factory, job_id, token, 'succeeded', result=result,
                                 publish=getattr(handler, 'publish', None)):
                raise ValueError('Late result rejected')
    except Exception:
        if workspace is not None and hasattr(handler, 'final_poll'):
            try:
                handler.final_poll(factory, job, token, workspace)
            except Exception:
                pass  # Preserve process fencing even when transcript storage is unavailable.
        if exited or not spawning:
            _exit(factory, job_id, token)
            _fail(factory, job_id, token, error=failure)
        else:
            # execute may have spawned before its callback failed. Never infer exit.
            with factory.begin() as session:
                job = claims.locked_job(session, job_id)
                if job and job.claim_token == token and job.status in ACTIVE:
                    claims.mark_uncertain(session, job)
